# Kafka Notifications And SDK Listener Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-phase asset event notification delivery through Kafka and Java SDK listener callbacks.

**Architecture:** Extend the existing Spring Boot JDBC style. `data-gov-common` owns notification DTOs/enums, `data-gov-server` owns event persistence, subscription matching, notification persistence, and Kafka publishing, while `data-gov-sdk` owns callback interfaces and a Spring Kafka listener. Tests must not require a real Kafka broker.

**Tech Stack:** Java 17, Spring Boot 3.3, JDBC/JdbcTemplate, Flyway, H2 tests, Spring Kafka, MockMvc, Spring Boot auto-configuration tests.

---

## Completion Status

Completed and verified on 2026-06-12:

- `cd data-gov-platform; mvn test` -> `BUILD SUCCESS`; server 40 tests passed, SDK 15 tests passed.
- `git diff --check` -> no whitespace errors.
- `git status --short -- app-compose.yml docker-compose.yml compose.yaml data-gov-platform\app-compose.yml` -> no infrastructure file changes.
- `git status --short` -> clean worktree before this documentation status update.

## Scope

Build this phase:

- `asset_event` and `subscription_notification` tables.
- `POST /api/assets/{assetCode}/events`.
- Active subscription matching by `asset_id`, `status = ACTIVE`, and `notify_on` containing the event type.
- Kafka publishing to `data-gov.subscription-notifications`.
- Notification status updates: `PENDING`, `SENT`, `FAILED`.
- Java SDK callback interface and Spring Kafka listener wiring.
- Tests proving matching, non-matching, failed publish, and SDK callback behavior.

Do not build this phase:

- `GET /api/notifications` or ack APIs.
- Drift detection.
- Webhook, email, IM, or approval workflows.
- Flink/Spark job run lifecycle records.
- Frontend UI.
- Docker Compose or shared infrastructure changes.

## Existing Context

Current modules:

- `data-gov-platform/data-gov-common`: DTOs and enums.
- `data-gov-platform/data-gov-server`: Spring Boot server, Flyway migrations, JDBC repositories.
- `data-gov-platform/data-gov-sdk`: Java SDK and Spring Boot auto-configuration.

Existing relevant tables:

- `data_asset`
- `consumer`
- `subscription`
- `query_record`
- `lineage_edge`

Existing relevant code:

- `GovernanceDtos.SubscriptionResponse.notifyOn()` already stores `List<AssetEventType>`.
- `SubscriptionRepository` serializes `notify_on` as JSON text.
- `ApiExceptionHandler` maps domain exceptions to JSON error responses.
- `DataGovAutoConfiguration` creates `DataGovClient` and startup registration.

## API Contract

Add endpoint:

```http
POST /api/assets/{assetCode}/events
```

Request:

```json
{
  "eventType": "SCHEMA_CHANGE",
  "severity": "WARN",
  "payload": {
    "changedFields": ["coverage_score"],
    "summary": "coverage_score type changed"
  }
}
```

Response:

```json
{
  "event": {
    "eventId": "evt_xxx",
    "assetId": "asset_xxx",
    "assetCode": "ads_cell_profile",
    "eventType": "SCHEMA_CHANGE",
    "severity": "WARN",
    "payload": {
      "changedFields": ["coverage_score"],
      "summary": "coverage_score type changed"
    },
    "createdAt": "2026-06-11T00:00:00Z"
  },
  "notifications": [
    {
      "notificationId": "ntf_xxx",
      "eventId": "evt_xxx",
      "subscriptionId": "sub_xxx",
      "consumerId": "consumer_xxx",
      "consumerName": "rno-dashboard",
      "status": "SENT",
      "kafkaTopic": "data-gov.subscription-notifications",
      "createdAt": "2026-06-11T00:00:00Z",
      "sentAt": "2026-06-11T00:00:00Z",
      "errorMessage": null
    }
  ]
}
```

Kafka message:

```json
{
  "notificationId": "ntf_xxx",
  "eventId": "evt_xxx",
  "assetCode": "ads_cell_profile",
  "eventType": "SCHEMA_CHANGE",
  "severity": "WARN",
  "payload": {
    "changedFields": ["coverage_score"]
  },
  "subscriptionId": "sub_xxx",
  "consumerId": "consumer_xxx",
  "consumerName": "rno-dashboard",
  "createdAt": "2026-06-11T00:00:00Z"
}
```

## Data Model

Add Flyway migration:

- `data-gov-platform/data-gov-server/src/main/resources/db/migration/V5__asset_events_and_notifications.sql`

```sql
create table asset_event (
    event_id varchar(64) primary key,
    asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    event_type varchar(64) not null,
    event_payload text,
    severity varchar(32),
    created_at timestamp not null
);

create index idx_asset_event_asset_id on asset_event(asset_id);
create index idx_asset_event_type on asset_event(event_type);
create index idx_asset_event_created_at on asset_event(created_at);

create table subscription_notification (
    notification_id varchar(64) primary key,
    event_id varchar(64) not null references asset_event(event_id) on delete cascade,
    subscription_id varchar(64) not null references subscription(subscription_id) on delete cascade,
    consumer_id varchar(64) not null references consumer(consumer_id) on delete cascade,
    status varchar(32) not null,
    kafka_topic varchar(256) not null,
    error_message text,
    created_at timestamp not null,
    sent_at timestamp
);

create index idx_subscription_notification_event_id on subscription_notification(event_id);
create index idx_subscription_notification_subscription_id on subscription_notification(subscription_id);
create index idx_subscription_notification_consumer_id on subscription_notification(consumer_id);
create index idx_subscription_notification_status on subscription_notification(status);
```

## DTOs And Enums

Add enum:

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/NotificationStatus.java`

```java
package io.datagov.common.enums;

public enum NotificationStatus {
    PENDING,
    SENT,
    FAILED
}
```

Add DTO:

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/EventDtos.java`

```java
package io.datagov.common.dto;

import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.NotificationStatus;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class EventDtos {
    private EventDtos() {
    }

    public record CreateAssetEventRequest(
            @NotNull AssetEventType eventType,
            String severity,
            Map<String, Object> payload
    ) {
    }

    public record AssetEventResponse(
            String eventId,
            String assetId,
            String assetCode,
            AssetEventType eventType,
            String severity,
            Map<String, Object> payload,
            Instant createdAt
    ) {
    }

    public record SubscriptionNotificationResponse(
            String notificationId,
            String eventId,
            String subscriptionId,
            String consumerId,
            String consumerName,
            NotificationStatus status,
            String kafkaTopic,
            Instant createdAt,
            Instant sentAt,
            String errorMessage
    ) {
    }

    public record CreateAssetEventResponse(
            AssetEventResponse event,
            List<SubscriptionNotificationResponse> notifications
    ) {
    }

    public record NotificationMessage(
            String notificationId,
            String eventId,
            String assetCode,
            AssetEventType eventType,
            String severity,
            Map<String, Object> payload,
            String subscriptionId,
            String consumerId,
            String consumerName,
            Instant createdAt
    ) {
    }
}
```

## Server Package Layout

Create package:

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/event`

Classes:

- `EventController`
- `EventService`
- `EventRepository`
- `EventDataAccessException`
- `NotificationPublisher`
- `KafkaNotificationPublisher`
- `NotificationProperties`

Modify:

- `data-gov-platform/data-gov-server/pom.xml`
- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`

Tests:

- `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/event/EventControllerTest.java`

## Server Behavior

`POST /api/assets/{assetCode}/events`:

1. Resolve asset by `assetCode`; missing assets use existing `AssetNotFoundException`.
2. Insert `asset_event`.
3. Find matching subscriptions:
   - same `asset_id`
   - `status = 'ACTIVE'`
   - `notify_on` JSON text contains exact event enum token.
4. Insert one `subscription_notification` per matching subscription with status `PENDING`.
5. Publish `EventDtos.NotificationMessage` to Kafka topic.
6. On completed publish future, update notification to `SENT` and set `sent_at`.
7. On failed publish future or immediate exception, update notification to `FAILED` and set `error_message`.
8. Return event and current notification statuses.

Use text matching for `notify_on` only as a first-phase lightweight implementation. Escape `%`, `_`, and `\` in the event token and use `escape '\'`, following the lineage impact query pattern.

## SDK Layout

Create:

- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/notification/DataGovNotificationHandler.java`
- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/notification/DataGovNotificationListener.java`

Modify:

- `data-gov-platform/data-gov-sdk/pom.xml`
- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovProperties.java`
- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovAutoConfiguration.java`

Tests:

- `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/notification/DataGovNotificationListenerTest.java`
- `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/spring/DataGovNotificationAutoConfigurationTest.java`

SDK behavior:

- Applications provide one or more `DataGovNotificationHandler` beans.
- SDK creates `DataGovNotificationListener` when `data-gov.notifications.enabled=true`.
- Listener receives `EventDtos.NotificationMessage` and invokes handlers.
- If one handler throws, remaining handlers are still invoked, and the listener throws after all handlers have been attempted.

## Task 1: Common Notification Contracts And Migration

**Files:**

- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/NotificationStatus.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/EventDtos.java`
- Create: `data-gov-platform/data-gov-server/src/main/resources/db/migration/V5__asset_events_and_notifications.sql`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/event/EventSchemaMigrationTest.java`

- [x] **Step 1: Write the failing migration/DTO contract test**

Create `EventSchemaMigrationTest.java`:

```java
package io.datagov.server.event;

import io.datagov.common.dto.EventDtos;
import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.NotificationStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
class EventSchemaMigrationTest {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void eventTablesAndDtosAreAvailable() {
        Integer eventTableCount = jdbcTemplate.queryForObject(
                "select count(*) from information_schema.tables where table_name = 'ASSET_EVENT'",
                Integer.class);
        Integer notificationTableCount = jdbcTemplate.queryForObject(
                "select count(*) from information_schema.tables where table_name = 'SUBSCRIPTION_NOTIFICATION'",
                Integer.class);

        EventDtos.NotificationMessage message = new EventDtos.NotificationMessage(
                "ntf_1",
                "evt_1",
                "ads_cell_profile",
                AssetEventType.SCHEMA_CHANGE,
                "WARN",
                Map.of("field", "coverage_score"),
                "sub_1",
                "consumer_1",
                "rno-dashboard",
                Instant.parse("2026-06-11T00:00:00Z"));

        EventDtos.CreateAssetEventResponse response = new EventDtos.CreateAssetEventResponse(
                new EventDtos.AssetEventResponse(
                        "evt_1",
                        "asset_1",
                        "ads_cell_profile",
                        AssetEventType.SCHEMA_CHANGE,
                        "WARN",
                        Map.of("field", "coverage_score"),
                        message.createdAt()),
                List.of(new EventDtos.SubscriptionNotificationResponse(
                        "ntf_1",
                        "evt_1",
                        "sub_1",
                        "consumer_1",
                        "rno-dashboard",
                        NotificationStatus.SENT,
                        "data-gov.subscription-notifications",
                        message.createdAt(),
                        message.createdAt(),
                        null)));

        assertThat(eventTableCount).isEqualTo(1);
        assertThat(notificationTableCount).isEqualTo(1);
        assertThat(response.notifications()).hasSize(1);
        assertThat(message.eventType()).isEqualTo(AssetEventType.SCHEMA_CHANGE);
    }
}
```

- [x] **Step 2: Run the test and verify red**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=EventSchemaMigrationTest test
```

Expected: fails because `EventDtos`, `NotificationStatus`, and V5 tables do not exist.

- [x] **Step 3: Add enum, DTO, and V5 migration**

Create the exact `NotificationStatus.java`, `EventDtos.java`, and `V5__asset_events_and_notifications.sql` from the sections above.

- [x] **Step 4: Run the test and verify green**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=EventSchemaMigrationTest test
```

Expected: `BUILD SUCCESS`.

## Task 2: Server Event API And Kafka Publisher

**Files:**

- Modify: `data-gov-platform/data-gov-server/pom.xml`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/event/EventController.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/event/EventService.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/event/EventRepository.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/event/EventDataAccessException.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/event/NotificationPublisher.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/event/KafkaNotificationPublisher.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/event/NotificationProperties.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/event/EventControllerTest.java`

- [x] **Step 1: Add Spring Kafka dependency**

Add to `data-gov-platform/data-gov-server/pom.xml`:

```xml
<dependency>
    <groupId>org.springframework.kafka</groupId>
    <artifactId>spring-kafka</artifactId>
</dependency>
```

- [x] **Step 2: Write failing EventController tests**

Create `EventControllerTest.java`:

```java
package io.datagov.server.event;

import io.datagov.common.dto.EventDtos;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class EventControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @MockBean
    private NotificationPublisher notificationPublisher;

    @Test
    void eventCreatesNotificationForMatchingActiveSubscriptionAndPublishesKafkaMessage() throws Exception {
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"), any(EventDtos.NotificationMessage.class)))
                .thenReturn(CompletableFuture.completedFuture(null));
        registerTableAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard", "SCHEMA_CHANGE");

        mockMvc.perform(post("/api/assets/ads_cell_profile/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "eventType": "SCHEMA_CHANGE",
                                  "severity": "WARN",
                                  "payload": {
                                    "changedFields": ["coverage_score"]
                                  }
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.event.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.event.eventType").value("SCHEMA_CHANGE"))
                .andExpect(jsonPath("$.notifications", hasSize(1)))
                .andExpect(jsonPath("$.notifications[0].consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.notifications[0].status").value("SENT"));

        Integer sentCount = jdbcTemplate.queryForObject(
                "select count(*) from subscription_notification where status = 'SENT'",
                Integer.class);
        assertThat(sentCount).isEqualTo(1);
    }

    @Test
    void eventDoesNotNotifyWhenNotifyOnDoesNotContainEventType() throws Exception {
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"), any(EventDtos.NotificationMessage.class)))
                .thenReturn(CompletableFuture.completedFuture(null));
        registerTableAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard", "DEPRECATION");

        mockMvc.perform(post("/api/assets/ads_cell_profile/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "eventType": "SCHEMA_CHANGE"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.notifications", hasSize(0)));
    }

    @Test
    void eventDoesNotNotifyInactiveSubscription() throws Exception {
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"), any(EventDtos.NotificationMessage.class)))
                .thenReturn(CompletableFuture.completedFuture(null));
        registerTableAsset("ads_cell_profile");
        String subscriptionId = createSubscription("ads_cell_profile", "rno-dashboard", "SCHEMA_CHANGE");
        jdbcTemplate.update("update subscription set status = 'PAUSED' where subscription_id = ?", subscriptionId);

        mockMvc.perform(post("/api/assets/ads_cell_profile/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "eventType": "SCHEMA_CHANGE"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.notifications", hasSize(0)));
    }

    @Test
    void failedPublishMarksNotificationFailed() throws Exception {
        CompletableFuture<Void> failed = new CompletableFuture<>();
        failed.completeExceptionally(new IllegalStateException("broker unavailable"));
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"), any(EventDtos.NotificationMessage.class)))
                .thenReturn(failed);
        registerTableAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard", "SCHEMA_CHANGE");

        mockMvc.perform(post("/api/assets/ads_cell_profile/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "eventType": "SCHEMA_CHANGE"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.notifications", hasSize(1)))
                .andExpect(jsonPath("$.notifications[0].status").value("FAILED"));

        Integer failedCount = jdbcTemplate.queryForObject(
                "select count(*) from subscription_notification where status = 'FAILED' and error_message is not null",
                Integer.class);
        assertThat(failedCount).isEqualTo(1);
    }

    private void registerTableAsset(String assetCode) throws Exception {
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "%s",
                                  "assetName": "%s",
                                  "assetType": "TABLE",
                                  "engine": "STARROCKS",
                                  "lifecycleStatus": "ACTIVE"
                                }
                                """.formatted(assetCode, assetCode)))
                .andExpect(status().isOk());
    }

    private String createSubscription(String assetCode, String consumerName, String notifyOn) throws Exception {
        String body = mockMvc.perform(post("/api/assets/{assetCode}/subscriptions", assetCode)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "%s",
                                    "consumerType": "MICROSERVICE",
                                    "environment": "prod"
                                  },
                                  "subscription": {
                                    "assetCode": "%s",
                                    "usageMode": "API_QUERY",
                                    "notifyOn": ["%s"]
                                  }
                                }
                                """.formatted(consumerName, assetCode, notifyOn)))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();
        return com.jayway.jsonpath.JsonPath.read(body, "$.subscriptionId");
    }
}
```

- [x] **Step 3: Run tests and verify red**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=EventControllerTest test
```

Expected: fails because event server package and endpoint do not exist.

- [x] **Step 4: Implement event repository/service/controller and publisher**

Implement these signatures:

```java
public interface NotificationPublisher {
    CompletableFuture<Void> publish(String topic, EventDtos.NotificationMessage message);
}
```

```java
@ConfigurationProperties(prefix = "data-gov.notifications")
public class NotificationProperties {
    private String kafkaTopic = "data-gov.subscription-notifications";
    // getter/setter and topic() accessor
}
```

```java
@RestController
@RequestMapping("/api")
public class EventController {
    @PostMapping("/assets/{assetCode}/events")
    public EventDtos.CreateAssetEventResponse createEvent(
            @PathVariable String assetCode,
            @Valid @RequestBody EventDtos.CreateAssetEventRequest request)
}
```

Repository methods:

```java
EventDtos.AssetEventResponse insertEvent(AssetDtos.AssetResponse asset, EventDtos.CreateAssetEventRequest request, Instant now);
List<MatchingSubscription> findMatchingSubscriptions(String assetId, AssetEventType eventType);
EventDtos.SubscriptionNotificationResponse insertNotification(...);
EventDtos.SubscriptionNotificationResponse markNotificationSent(String notificationId, Instant sentAt);
EventDtos.SubscriptionNotificationResponse markNotificationFailed(String notificationId, String errorMessage);
```

`MatchingSubscription` should carry `subscriptionId`, `consumerId`, and `consumerName`.

`KafkaNotificationPublisher` should use `KafkaTemplate<String, EventDtos.NotificationMessage>`:

```java
@Component
public class KafkaNotificationPublisher implements NotificationPublisher {
    private final KafkaTemplate<String, EventDtos.NotificationMessage> kafkaTemplate;

    public CompletableFuture<Void> publish(String topic, EventDtos.NotificationMessage message) {
        return kafkaTemplate.send(topic, message.notificationId(), message).thenApply(result -> null);
    }
}
```

Add `EventDataAccessException` and an `ApiExceptionHandler` method mapping it to HTTP 500 with error `EVENT_DATA_ACCESS_ERROR`.

- [x] **Step 5: Run focused tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=EventControllerTest test
```

Expected: `BUILD SUCCESS`.

## Task 3: SDK Notification Listener

**Files:**

- Modify: `data-gov-platform/data-gov-sdk/pom.xml`
- Create: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/notification/DataGovNotificationHandler.java`
- Create: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/notification/DataGovNotificationListener.java`
- Modify: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovProperties.java`
- Modify: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovAutoConfiguration.java`
- Create: `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/notification/DataGovNotificationListenerTest.java`
- Create: `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/spring/DataGovNotificationAutoConfigurationTest.java`

- [x] **Step 1: Add Spring Kafka dependency**

Add to `data-gov-platform/data-gov-sdk/pom.xml`:

```xml
<dependency>
    <groupId>org.springframework.kafka</groupId>
    <artifactId>spring-kafka</artifactId>
</dependency>
```

- [x] **Step 2: Write failing listener tests**

Create `DataGovNotificationListenerTest.java`:

```java
package io.datagov.sdk.notification;

import io.datagov.common.dto.EventDtos;
import io.datagov.common.enums.AssetEventType;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DataGovNotificationListenerTest {
    @Test
    void dispatchesMessageToAllHandlers() {
        List<String> seen = new ArrayList<>();
        DataGovNotificationListener listener = new DataGovNotificationListener(List.of(
                message -> seen.add("first:" + message.assetCode()),
                message -> seen.add("second:" + message.eventType().name())
        ));

        listener.onMessage(message());

        assertThat(seen).containsExactly("first:ads_cell_profile", "second:SCHEMA_CHANGE");
    }

    @Test
    void invokesRemainingHandlersWhenOneHandlerFailsThenThrows() {
        List<String> seen = new ArrayList<>();
        DataGovNotificationListener listener = new DataGovNotificationListener(List.of(
                message -> {
                    throw new IllegalStateException("handler failed");
                },
                message -> seen.add(message.notificationId())
        ));

        assertThatThrownBy(() -> listener.onMessage(message()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Failed to handle data governance notification");
        assertThat(seen).containsExactly("ntf_1");
    }

    private EventDtos.NotificationMessage message() {
        return new EventDtos.NotificationMessage(
                "ntf_1",
                "evt_1",
                "ads_cell_profile",
                AssetEventType.SCHEMA_CHANGE,
                "WARN",
                Map.of("field", "coverage_score"),
                "sub_1",
                "consumer_1",
                "rno-dashboard",
                Instant.parse("2026-06-11T00:00:00Z"));
    }
}
```

Create `DataGovNotificationAutoConfigurationTest.java`:

```java
package io.datagov.sdk.spring;

import io.datagov.sdk.notification.DataGovNotificationHandler;
import io.datagov.sdk.notification.DataGovNotificationListener;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.assertj.core.api.Assertions.assertThat;

class DataGovNotificationAutoConfigurationTest {
    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withConfiguration(AutoConfigurations.of(DataGovAutoConfiguration.class));

    @Test
    void createsNotificationListenerWhenEnabledAndHandlerExists() {
        contextRunner
                .withBean(DataGovNotificationHandler.class, () -> message -> {
                })
                .withPropertyValues(
                        "data-gov.notifications.enabled=true",
                        "data-gov.notifications.topic=data-gov.subscription-notifications",
                        "data-gov.notifications.group-id=rno-dashboard")
                .run(context -> {
                    assertThat(context).hasSingleBean(DataGovNotificationListener.class);
                    DataGovProperties properties = context.getBean(DataGovProperties.class);
                    assertThat(properties.notifications().topic()).isEqualTo("data-gov.subscription-notifications");
                    assertThat(properties.notifications().groupId()).isEqualTo("rno-dashboard");
                });
    }

    @Test
    void doesNotCreateNotificationListenerByDefault() {
        contextRunner
                .withBean(DataGovNotificationHandler.class, () -> message -> {
                })
                .run(context -> assertThat(context).doesNotHaveBean(DataGovNotificationListener.class));
    }
}
```

- [x] **Step 3: Run tests and verify red**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-sdk -am -Dtest=DataGovNotificationListenerTest,DataGovNotificationAutoConfigurationTest test
```

Expected: fails because listener classes/properties do not exist.

- [x] **Step 4: Implement SDK listener and properties**

Create `DataGovNotificationHandler.java`:

```java
package io.datagov.sdk.notification;

import io.datagov.common.dto.EventDtos;

@FunctionalInterface
public interface DataGovNotificationHandler {
    void handle(EventDtos.NotificationMessage message);
}
```

Create `DataGovNotificationListener.java`:

```java
package io.datagov.sdk.notification;

import io.datagov.common.dto.EventDtos;
import org.springframework.kafka.annotation.KafkaListener;

import java.util.List;

public class DataGovNotificationListener {
    private final List<DataGovNotificationHandler> handlers;

    public DataGovNotificationListener(List<DataGovNotificationHandler> handlers) {
        this.handlers = handlers == null ? List.of() : List.copyOf(handlers);
    }

    @KafkaListener(
            topics = "${data-gov.notifications.topic:data-gov.subscription-notifications}",
            groupId = "${data-gov.notifications.group-id:data-gov-sdk}",
            autoStartup = "${data-gov.notifications.enabled:false}")
    public void onMessage(EventDtos.NotificationMessage message) {
        RuntimeException failure = null;
        for (DataGovNotificationHandler handler : handlers) {
            try {
                handler.handle(message);
            } catch (RuntimeException ex) {
                if (failure == null) {
                    failure = new IllegalStateException("Failed to handle data governance notification", ex);
                } else {
                    failure.addSuppressed(ex);
                }
            }
        }
        if (failure != null) {
            throw failure;
        }
    }
}
```

Add nested notification properties to `DataGovProperties`:

```java
private Notifications notifications = new Notifications();

public Notifications notifications() {
    return notifications;
}

public Notifications getNotifications() {
    return notifications;
}

public void setNotifications(Notifications notifications) {
    this.notifications = notifications == null ? new Notifications() : notifications;
}

public static class Notifications {
    private boolean enabled = false;
    private String topic = "data-gov.subscription-notifications";
    private String groupId = "data-gov-sdk";

    public boolean enabled() { return enabled; }
    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }
    public String topic() { return topic; }
    public String getTopic() { return topic; }
    public void setTopic(String topic) { this.topic = topic; }
    public String groupId() { return groupId; }
    public String getGroupId() { return groupId; }
    public void setGroupId(String groupId) { this.groupId = groupId; }
}
```

Add bean to `DataGovAutoConfiguration`:

```java
@Bean
@ConditionalOnProperty(prefix = "data-gov.notifications", name = "enabled", havingValue = "true")
@ConditionalOnBean(DataGovNotificationHandler.class)
@ConditionalOnMissingBean
public DataGovNotificationListener dataGovNotificationListener(List<DataGovNotificationHandler> handlers) {
    return new DataGovNotificationListener(handlers);
}
```

Import `DataGovNotificationHandler`, `DataGovNotificationListener`, `ConditionalOnBean`, and `ConditionalOnMissingBean` as needed.

- [x] **Step 5: Run focused SDK tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-sdk -am -Dtest=DataGovNotificationListenerTest,DataGovNotificationAutoConfigurationTest test
```

Expected: `BUILD SUCCESS`.

## Task 4: Full Verification

**Files:**

- Verify all files touched by Tasks 1-3.

- [x] **Step 1: Run full Maven tests**

Run:

```powershell
cd data-gov-platform
mvn test
```

Expected: `BUILD SUCCESS`.

- [x] **Step 2: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

- [x] **Step 3: Confirm no infrastructure files changed**

Run:

```powershell
git status --short -- app-compose.yml docker-compose.yml compose.yaml data-gov-platform\app-compose.yml
```

Expected: no output.

If infrastructure files are changed, revert only those changes if they were created by this notifications phase. Do not revert unrelated user changes.

## Review Checklist

Before merge:

- V5 migration creates `asset_event` and `subscription_notification`.
- `POST /api/assets/{assetCode}/events` persists events and notifications.
- Only active subscriptions with matching `notify_on` receive notifications.
- Kafka publisher is asynchronous and updates notification status.
- SDK listener dispatches Kafka messages to callbacks.
- No notification pull/ack API was added.
- No drift detection was added.
- No Docker Compose files were changed.

## Plan Self-Review

Spec coverage:

- Event notification value of subscriptions: Tasks 1 and 2.
- Kafka async publishing: Task 2.
- SDK listener callback: Task 3.
- No API pull/ack: no task adds those endpoints.
- No drift: no task adds governance drift tables or APIs.
- No Docker Compose changes: Task 4 explicitly checks.

Placeholder scan:

- The plan contains no unresolved placeholders or deferred implementation steps.

Type consistency:

- `AssetEventType` is reused from existing subscription declarations.
- `NotificationStatus` is shared by server and common DTOs.
- Kafka message type is `EventDtos.NotificationMessage` in server and SDK.
