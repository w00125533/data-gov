# Formal Subscription And Query API Implementation Plan

> **Execution note:** This plan used superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Steps now use checked checkbox (`- [x]`) syntax to reflect completed execution.

**Goal:** Add the formal `/rest/oss/inner/modelengineservice/v1` subscription and query API slice so callers can create, list, cancel, and use subscriptions by `metadataId`.

**Architecture:** Keep the existing `/api` controllers and services as the compatibility layer. Add focused formal controllers that resolve `metadataId` through `AssetRepository.findAssetById(...)`, map formal request bodies to existing service contracts, and add small repository/service methods for asset-scoped subscription listing and cancellation.

**Tech Stack:** Java 17, Spring Boot 3.3, Spring MVC, Jakarta Validation, JDBC `JdbcTemplate`, H2/Flyway test database, MockMvc, Maven.

## Execution Status

Executed on `master` on 2026-06-13. Implementation commits: `7b11c05`, `3e9fea4`, `8a69465`, `2071829`, `64d3397`, `32e4df0`. Follow-up fix commit will be added after this task if available.

---

## Scope

This phase implements:

- `POST /rest/oss/inner/modelengineservice/v1/subscriptions/{metadataId}`
- `GET /rest/oss/inner/modelengineservice/v1/subscriptions/{metadataId}`
- `DELETE /rest/oss/inner/modelengineservice/v1/subscriptions/{metadataId}`
- `POST /rest/oss/inner/modelengineservice/v1/apiquery/{metadataId}`
- `POST /rest/oss/inner/modelengineservice/v1/sqlquery`

This phase does not change Docker Compose infrastructure, shared-data-infra, frontend pages, Kafka notification delivery, lineage APIs, or SDK startup subscription routing. The SDK formal subscription wrapper remains a later phase because it needs client-side metadata ID discovery or configuration.

## Existing Code To Preserve

- Existing `/api/assets/{assetCode}/subscriptions`, `/api/subscriptions`, `/api/assets/{assetCode}/query`, and `/api/sql` routes must keep their current request and response shapes.
- Existing `SubscriptionStatus.PAUSED`, `STALE`, and `REVOKED` must remain valid because current tests and drift behavior reference them.
- Existing query record behavior must remain unchanged: product API and SQL Gateway attempts record success and failure in `query_record`.
- Existing formal metadata controller at `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataController.java` already owns the `/rest/oss/inner/modelengineservice/v1` prefix for metadata only.

## File Structure

- Modify `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/SubscriptionStatus.java`
  - Add formal cancellation statuses without removing legacy statuses.
- Create `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/FormalSubscriptionDtos.java`
  - Shared formal subscription request and response records.
- Create `data-gov-platform/data-gov-common/src/test/java/io/datagov/common/dto/FormalSubscriptionDtosContractTest.java`
  - Contract tests for formal DTO JSON shape and status enum availability.
- Modify `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionRepository.java`
  - Add asset-scoped list and consumer-scoped cancellation methods.
- Modify `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionService.java`
  - Add formal create/list/cancel methods that reuse current upsert logic.
- Create `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/FormalSubscriptionController.java`
  - Formal subscription REST endpoints under `/rest/oss/inner/modelengineservice/v1`.
- Create `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/query/FormalQueryController.java`
  - Formal query REST endpoints under `/rest/oss/inner/modelengineservice/v1`.
- Create `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/subscription/FormalSubscriptionControllerTest.java`
  - MockMvc coverage for formal create/list/cancel flows.
- Create `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/query/FormalQueryControllerTest.java`
  - MockMvc coverage for formal API query, header subscription ID handling, and formal SQL query.

## Task 1: Formal Subscription DTO Contract

**Files:**
- Modify: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/SubscriptionStatus.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/FormalSubscriptionDtos.java`
- Create: `data-gov-platform/data-gov-common/src/test/java/io/datagov/common/dto/FormalSubscriptionDtosContractTest.java`

- [x] **Step 1: Add the failing DTO contract test**

Create `data-gov-platform/data-gov-common/src/test/java/io/datagov/common/dto/FormalSubscriptionDtosContractTest.java`:

```java
package io.datagov.common.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.common.enums.UsageMode;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class FormalSubscriptionDtosContractTest {
    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

    @Test
    void formalCreateSubscriptionRequestDeserializesFlatBody() throws Exception {
        FormalSubscriptionDtos.FormalCreateSubscriptionRequest request = objectMapper.readValue("""
                {
                  "consumer": {
                    "consumerName": "rno-dashboard",
                    "consumerType": "MICROSERVICE",
                    "owner": "network-team",
                    "environment": "prod"
                  },
                  "usageMode": "API_QUERY",
                  "purpose": "dashboard display",
                  "fields": ["cell_id", "coverage_score"],
                  "notifyOn": ["SCHEMA_CHANGE", "DEPRECATION"],
                  "notificationStrategy": {
                    "delivery": "KAFKA",
                    "sdkCallback": true,
                    "consumerGroup": "rno-dashboard"
                  }
                }
                """, FormalSubscriptionDtos.FormalCreateSubscriptionRequest.class);

        assertThat(request.consumer().consumerName()).isEqualTo("rno-dashboard");
        assertThat(request.consumer().consumerType()).isEqualTo(ConsumerType.MICROSERVICE);
        assertThat(request.usageMode()).isEqualTo(UsageMode.API_QUERY);
        assertThat(request.fields()).containsExactly("cell_id", "coverage_score");
        assertThat(request.notifyOn()).containsExactly(AssetEventType.SCHEMA_CHANGE, AssetEventType.DEPRECATION);
        assertThat(request.notificationStrategy().delivery()).isEqualTo("KAFKA");
        assertThat(request.notificationStrategy().sdkCallback()).isTrue();
    }

    @Test
    void formalSubscriptionResponseSerializesMetadataIdAndFields() throws Exception {
        FormalSubscriptionDtos.FormalSubscriptionResponse response =
                new FormalSubscriptionDtos.FormalSubscriptionResponse(
                        "sub_001",
                        "metadata_001",
                        "ads_cell_profile",
                        "consumer_001",
                        UsageMode.API_QUERY,
                        SubscriptionStatus.ACTIVE,
                        List.of("cell_id"),
                        List.of(AssetEventType.SCHEMA_CHANGE),
                        Instant.parse("2026-06-11T00:00:00Z"));

        String json = objectMapper.writeValueAsString(response);

        assertThat(json).contains("\"metadataId\":\"metadata_001\"");
        assertThat(json).contains("\"fields\":[\"cell_id\"]");
        assertThat(json).contains("\"status\":\"ACTIVE\"");
    }

    @Test
    void formalCancellationStatusesAreAvailable() {
        assertThat(SubscriptionStatus.valueOf("CANCELLED")).isEqualTo(SubscriptionStatus.CANCELLED);
        assertThat(SubscriptionStatus.valueOf("REMOVED_BY_SNAPSHOT"))
                .isEqualTo(SubscriptionStatus.REMOVED_BY_SNAPSHOT);
    }
}
```

- [x] **Step 2: Run the common module test and confirm it fails**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-common -Dtest=FormalSubscriptionDtosContractTest test
```

Expected: compilation fails because `FormalSubscriptionDtos`, `SubscriptionStatus.CANCELLED`, and `SubscriptionStatus.REMOVED_BY_SNAPSHOT` do not exist.

- [x] **Step 3: Extend `SubscriptionStatus`**

Replace `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/SubscriptionStatus.java` with:

```java
package io.datagov.common.enums;

public enum SubscriptionStatus {
    ACTIVE,
    STALE,
    PAUSED,
    REVOKED,
    CANCELLED,
    REMOVED_BY_SNAPSHOT
}
```

- [x] **Step 4: Add formal subscription DTOs**

Create `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/FormalSubscriptionDtos.java`:

```java
package io.datagov.common.dto;

import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.common.enums.UsageMode;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;

public final class FormalSubscriptionDtos {
    private FormalSubscriptionDtos() {
    }

    public record NotificationStrategyRequest(
            String delivery,
            Boolean sdkCallback,
            String consumerGroup
    ) {
    }

    public record FormalCreateSubscriptionRequest(
            @Valid @NotNull GovernanceDtos.ConsumerRequest consumer,
            @NotNull UsageMode usageMode,
            @NotBlank String purpose,
            List<String> fields,
            List<AssetEventType> notifyOn,
            NotificationStrategyRequest notificationStrategy
    ) {
    }

    public record FormalCancelSubscriptionRequest(
            @NotBlank String consumerId,
            @NotBlank String reason,
            @NotBlank String operator
    ) {
    }

    public record FormalSubscriptionResponse(
            String subscriptionId,
            String metadataId,
            String assetCode,
            String consumerId,
            UsageMode usageMode,
            SubscriptionStatus status,
            List<String> fields,
            List<AssetEventType> notifyOn,
            Instant createdAt
    ) {
    }

    public record FormalSubscriptionListResponse(
            String metadataId,
            List<FormalSubscriptionResponse> items,
            int page,
            int size,
            int total
    ) {
    }

    public record CancelledSubscriptionResponse(
            String subscriptionId,
            SubscriptionStatus status
    ) {
    }

    public record FormalCancelSubscriptionResponse(
            String metadataId,
            String consumerId,
            List<CancelledSubscriptionResponse> cancelledSubscriptions,
            Instant cancelledAt
    ) {
    }
}
```

- [x] **Step 5: Run the common module test and commit**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-common -Dtest=FormalSubscriptionDtosContractTest test
```

Expected: `BUILD SUCCESS`.

Commit:

```powershell
git add data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/SubscriptionStatus.java `
        data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/FormalSubscriptionDtos.java `
        data-gov-platform/data-gov-common/src/test/java/io/datagov/common/dto/FormalSubscriptionDtosContractTest.java
git commit -m "Add formal subscription contracts"
```

## Task 2: Asset-Scoped Subscription Repository And Service

**Files:**
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionRepository.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionService.java`

- [x] **Step 1: Add repository methods**

In `SubscriptionRepository`, add these imports if absent:

```java
import java.util.ArrayList;
```

Add these methods after `listSubscriptions()`:

```java
public List<GovernanceDtos.SubscriptionResponse> listSubscriptionsForAsset(
        String assetId,
        String consumerId,
        SubscriptionStatus status
) {
    List<Object> args = new ArrayList<>();
    args.add(assetId);
    StringBuilder sql = new StringBuilder("""
            select s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name, s.usage_mode,
                   s.purpose, s.declared_fields, s.notify_on, s.source_type, s.status, s.declaration_hash,
                   s.last_registered_at, s.last_runtime_seen_at, s.created_at, s.updated_at
            from subscription s
            join data_asset a on a.asset_id = s.asset_id
            join consumer c on c.consumer_id = s.consumer_id
            where s.asset_id = ?
            """);
    if (consumerId != null && !consumerId.isBlank()) {
        sql.append(" and s.consumer_id = ?");
        args.add(consumerId);
    }
    if (status != null) {
        sql.append(" and s.status = ?");
        args.add(status.name());
    }
    sql.append(" order by s.created_at, s.subscription_id");
    return jdbcTemplate.query(sql.toString(), subscriptionMapper(), args.toArray());
}

public List<GovernanceDtos.SubscriptionResponse> cancelSubscriptionsForAssetAndConsumer(
        String assetId,
        String consumerId,
        Instant now
) {
    List<GovernanceDtos.SubscriptionResponse> current = listSubscriptionsForAsset(assetId, consumerId, null).stream()
            .filter(subscription -> subscription.status() != SubscriptionStatus.CANCELLED)
            .filter(subscription -> subscription.status() != SubscriptionStatus.REMOVED_BY_SNAPSHOT)
            .toList();
    for (GovernanceDtos.SubscriptionResponse subscription : current) {
        jdbcTemplate.update("""
                update subscription
                set status = ?, updated_at = ?
                where subscription_id = ?
                """,
                SubscriptionStatus.CANCELLED.name(),
                Timestamp.from(now),
                subscription.subscriptionId());
    }
    return current.stream()
            .map(subscription -> findSubscription(subscription.subscriptionId()).orElseThrow())
            .toList();
}
```

- [x] **Step 2: Add service methods**

In `SubscriptionService`, add imports:

```java
import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.FormalSubscriptionDtos;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.server.asset.AssetRepository;
```

Add a field:

```java
private final AssetRepository assetRepository;
```

Change the constructor to accept and assign `AssetRepository`:

```java
public SubscriptionService(
        SubscriptionRepository subscriptionRepository,
        TransactionTemplate transactionTemplate,
        AssetRepository assetRepository
) {
    this.subscriptionRepository = subscriptionRepository;
    this.transactionTemplate = transactionTemplate;
    this.assetRepository = assetRepository;
}
```

Add these public methods after `updateSubscription(...)`:

```java
public FormalSubscriptionDtos.FormalSubscriptionResponse createFormalSubscription(
        String metadataId,
        FormalSubscriptionDtos.FormalCreateSubscriptionRequest request
) {
    AssetDtos.AssetResponse asset = requireAssetById(metadataId);
    GovernanceDtos.SubscriptionDeclarationRequest declaration =
            new GovernanceDtos.SubscriptionDeclarationRequest(
                    asset.assetCode(),
                    request.usageMode(),
                    request.purpose(),
                    request.fields(),
                    request.notifyOn());
    GovernanceDtos.SubscriptionResponse subscription = createSubscription(
            asset.assetCode(),
            new GovernanceDtos.CreateSubscriptionRequest(request.consumer(), declaration));
    return toFormalResponse(metadataId, subscription);
}

public FormalSubscriptionDtos.FormalSubscriptionListResponse listFormalSubscriptions(
        String metadataId,
        String consumerId,
        SubscriptionStatus status,
        int page,
        int size
) {
    AssetDtos.AssetResponse asset = requireAssetById(metadataId);
    int cappedPage = Math.max(1, page);
    int cappedSize = Math.min(100, Math.max(1, size));
    List<FormalSubscriptionDtos.FormalSubscriptionResponse> items = subscriptionRepository
            .listSubscriptionsForAsset(asset.assetId(), consumerId, status)
            .stream()
            .map(subscription -> toFormalResponse(metadataId, subscription))
            .toList();
    long offset = ((long) cappedPage - 1L) * cappedSize;
    int fromIndex = offset >= items.size() ? items.size() : (int) offset;
    int toIndex = (int) Math.min(items.size(), offset + cappedSize);
    return new FormalSubscriptionDtos.FormalSubscriptionListResponse(
            metadataId,
            items.subList(fromIndex, toIndex),
            cappedPage,
            cappedSize,
            items.size());
}

public FormalSubscriptionDtos.FormalCancelSubscriptionResponse cancelFormalSubscriptions(
        String metadataId,
        FormalSubscriptionDtos.FormalCancelSubscriptionRequest request
) {
    return transactionTemplate.execute(status -> {
        AssetDtos.AssetResponse asset = requireAssetById(metadataId);
        Instant now = Instant.now();
        List<FormalSubscriptionDtos.CancelledSubscriptionResponse> cancelledSubscriptions =
                subscriptionRepository.cancelSubscriptionsForAssetAndConsumer(
                                asset.assetId(),
                                request.consumerId(),
                                now)
                        .stream()
                        .map(subscription -> new FormalSubscriptionDtos.CancelledSubscriptionResponse(
                                subscription.subscriptionId(),
                                subscription.status()))
                        .toList();
        return new FormalSubscriptionDtos.FormalCancelSubscriptionResponse(
                metadataId,
                request.consumerId(),
                cancelledSubscriptions,
                now);
    });
}
```

Add these private helpers near `requireAsset(...)`:

```java
private AssetDtos.AssetResponse requireAssetById(String metadataId) {
    return assetRepository.findAssetById(metadataId)
            .orElseThrow(() -> new AssetNotFoundException(metadataId));
}

private FormalSubscriptionDtos.FormalSubscriptionResponse toFormalResponse(
        String metadataId,
        GovernanceDtos.SubscriptionResponse subscription
) {
    return new FormalSubscriptionDtos.FormalSubscriptionResponse(
            subscription.subscriptionId(),
            metadataId,
            subscription.assetCode(),
            subscription.consumerId(),
            subscription.usageMode(),
            subscription.status(),
            subscription.declaredFields(),
            subscription.notifyOn(),
            subscription.createdAt());
}
```

- [x] **Step 3: Run focused existing subscription tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=SubscriptionControllerTest test
```

Expected: `BUILD SUCCESS`. The legacy `/api` subscription behavior remains intact.

- [x] **Step 4: Commit repository and service support**

Commit:

```powershell
git add data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionRepository.java `
        data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionService.java
git commit -m "Add asset scoped subscription operations"
```

## Task 3: Formal Subscription Controller

**Files:**
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/FormalSubscriptionController.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/subscription/FormalSubscriptionControllerTest.java`

- [x] **Step 1: Add the failing formal controller test**

Create `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/subscription/FormalSubscriptionControllerTest.java`:

```java
package io.datagov.server.subscription;

import com.jayway.jsonpath.JsonPath;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class FormalSubscriptionControllerTest {
    private static final String BASE_PATH = "/rest/oss/inner/modelengineservice/v1";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    private String metadataId;

    @BeforeEach
    void registerMetadata() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "producer": {
                                    "serviceName": "rno-profile-service",
                                    "serviceType": "MICROSERVICE",
                                    "environment": "prod",
                                    "owner": "network-team"
                                  },
                                  "syncMode": "FULL",
                                  "metadataList": [
                                    {
                                      "assetCode": "ads_cell_profile",
                                      "assetName": "ADS Cell Profile",
                                      "metadataType": "TABLE",
                                      "sourceType": "STARROCKS",
                                      "domain": "wireless",
                                      "owner": "network-team",
                                      "queryable": true,
                                      "federatedQueryable": true,
                                      "schema": [
                                        {"fieldName": "cell_id", "fieldType": "varchar", "ordinal": 1},
                                        {"fieldName": "coverage_score", "fieldType": "double", "ordinal": 2}
                                      ],
                                      "binding": {
                                        "sourceType": "STARROCKS",
                                        "catalog": "default_catalog",
                                        "database": "ads",
                                        "table": "ads_cell_profile",
                                        "queryAdapter": "starrocks"
                                      }
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk());
        metadataId = jdbcTemplate.queryForObject(
                "select asset_id from data_asset where asset_code = ?",
                String.class,
                "ads_cell_profile");
    }

    @Test
    void createListAndCancelFormalSubscriptionByMetadataId() throws Exception {
        String created = mockMvc.perform(post(BASE_PATH + "/subscriptions/{metadataId}", metadataId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "owner": "network-team",
                                    "environment": "prod"
                                  },
                                  "usageMode": "API_QUERY",
                                  "purpose": "dashboard display",
                                  "fields": ["cell_id", "coverage_score"],
                                  "notifyOn": ["SCHEMA_CHANGE", "DEPRECATION"],
                                  "notificationStrategy": {
                                    "delivery": "KAFKA",
                                    "sdkCallback": true,
                                    "consumerGroup": "rno-dashboard"
                                  }
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.subscriptionId", notNullValue()))
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andExpect(jsonPath("$.fields", hasSize(2)))
                .andReturn()
                .getResponse()
                .getContentAsString();

        String subscriptionId = JsonPath.read(created, "$.subscriptionId");
        String consumerId = JsonPath.read(created, "$.consumerId");

        mockMvc.perform(get(BASE_PATH + "/subscriptions/{metadataId}", metadataId)
                        .param("consumerId", consumerId)
                        .param("status", "ACTIVE")
                        .param("page", "1")
                        .param("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].subscriptionId").value(subscriptionId))
                .andExpect(jsonPath("$.items[0].fields[0]").value("cell_id"))
                .andExpect(jsonPath("$.total").value(1));

        mockMvc.perform(delete(BASE_PATH + "/subscriptions/{metadataId}", metadataId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumerId": "%s",
                                  "reason": "business retired",
                                  "operator": "network-team"
                                }
                                """.formatted(consumerId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.consumerId").value(consumerId))
                .andExpect(jsonPath("$.cancelledSubscriptions", hasSize(1)))
                .andExpect(jsonPath("$.cancelledSubscriptions[0].subscriptionId").value(subscriptionId))
                .andExpect(jsonPath("$.cancelledSubscriptions[0].status").value("CANCELLED"));

        mockMvc.perform(get(BASE_PATH + "/subscriptions/{metadataId}", metadataId)
                        .param("consumerId", consumerId)
                        .param("status", "CANCELLED"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].status").value("CANCELLED"));
    }

    @Test
    void formalSubscriptionMissingMetadataReturns404() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/subscriptions/{metadataId}", "missing_metadata")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "owner": "network-team",
                                    "environment": "prod"
                                  },
                                  "usageMode": "API_QUERY",
                                  "purpose": "dashboard display"
                                }
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
    }
}
```

- [x] **Step 2: Run the formal subscription test and confirm it fails**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=FormalSubscriptionControllerTest test
```

Expected: fails with 404 route mapping or missing controller class.

- [x] **Step 3: Add the controller**

Create `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/FormalSubscriptionController.java`:

```java
package io.datagov.server.subscription;

import io.datagov.common.dto.FormalSubscriptionDtos;
import io.datagov.common.enums.SubscriptionStatus;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/rest/oss/inner/modelengineservice/v1")
public class FormalSubscriptionController {
    private final SubscriptionService subscriptionService;

    public FormalSubscriptionController(SubscriptionService subscriptionService) {
        this.subscriptionService = subscriptionService;
    }

    @PostMapping("/subscriptions/{metadataId}")
    public FormalSubscriptionDtos.FormalSubscriptionResponse createSubscription(
            @PathVariable("metadataId") String metadataId,
            @Valid @RequestBody FormalSubscriptionDtos.FormalCreateSubscriptionRequest request
    ) {
        return subscriptionService.createFormalSubscription(metadataId, request);
    }

    @GetMapping("/subscriptions/{metadataId}")
    public FormalSubscriptionDtos.FormalSubscriptionListResponse listSubscriptions(
            @PathVariable("metadataId") String metadataId,
            @RequestParam(name = "consumerId", required = false) String consumerId,
            @RequestParam(name = "status", required = false) SubscriptionStatus status,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "size", defaultValue = "20") int size
    ) {
        return subscriptionService.listFormalSubscriptions(metadataId, consumerId, status, page, size);
    }

    @DeleteMapping("/subscriptions/{metadataId}")
    public FormalSubscriptionDtos.FormalCancelSubscriptionResponse cancelSubscriptions(
            @PathVariable("metadataId") String metadataId,
            @Valid @RequestBody FormalSubscriptionDtos.FormalCancelSubscriptionRequest request
    ) {
        return subscriptionService.cancelFormalSubscriptions(metadataId, request);
    }
}
```

- [x] **Step 4: Run formal and legacy subscription tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=FormalSubscriptionControllerTest,SubscriptionControllerTest test
```

Expected: `BUILD SUCCESS`.

- [x] **Step 5: Commit formal subscription routes**

Commit:

```powershell
git add data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/FormalSubscriptionController.java `
        data-gov-platform/data-gov-server/src/test/java/io/datagov/server/subscription/FormalSubscriptionControllerTest.java
git commit -m "Add formal subscription API"
```

## Task 4: Formal Query Controller

**Files:**
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/query/FormalQueryController.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/query/FormalQueryControllerTest.java`

- [x] **Step 1: Add the failing formal query controller test**

Create `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/query/FormalQueryControllerTest.java`:

```java
package io.datagov.server.query;

import com.jayway.jsonpath.JsonPath;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
class FormalQueryControllerTest {
    private static final String BASE_PATH = "/rest/oss/inner/modelengineservice/v1";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private FakeStarRocksQueryExecutor executor;

    private String metadataId;
    private String subscriptionId;

    @BeforeEach
    void registerMetadataAndSubscription() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "producer": {
                                    "serviceName": "rno-profile-service",
                                    "serviceType": "MICROSERVICE",
                                    "environment": "prod",
                                    "owner": "network-team"
                                  },
                                  "syncMode": "FULL",
                                  "metadataList": [
                                    {
                                      "assetCode": "ads_cell_profile",
                                      "assetName": "ADS Cell Profile",
                                      "metadataType": "TABLE",
                                      "sourceType": "STARROCKS",
                                      "domain": "wireless",
                                      "owner": "network-team",
                                      "queryable": true,
                                      "federatedQueryable": true,
                                      "schema": [
                                        {"fieldName": "cell_id", "fieldType": "varchar", "ordinal": 1},
                                        {"fieldName": "coverage_score", "fieldType": "double", "ordinal": 2},
                                        {"fieldName": "province", "fieldType": "varchar", "ordinal": 3}
                                      ],
                                      "binding": {
                                        "sourceType": "STARROCKS",
                                        "catalog": "default_catalog",
                                        "database": "ads",
                                        "table": "ads_cell_profile",
                                        "queryAdapter": "starrocks"
                                      }
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk());
        metadataId = jdbcTemplate.queryForObject(
                "select asset_id from data_asset where asset_code = ?",
                String.class,
                "ads_cell_profile");

        String createdSubscription = mockMvc.perform(post(BASE_PATH + "/subscriptions/{metadataId}", metadataId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "owner": "network-team",
                                    "environment": "prod"
                                  },
                                  "usageMode": "API_QUERY",
                                  "purpose": "dashboard display",
                                  "fields": ["cell_id"],
                                  "notifyOn": ["SCHEMA_CHANGE"]
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();
        subscriptionId = JsonPath.read(createdSubscription, "$.subscriptionId");
    }

    @Test
    void formalApiQueryResolvesMetadataIdAndHeaderSubscription() throws Exception {
        executor.result = new QueryResult(
                List.of("cell_id", "coverage_score"),
                List.of(Map.of("cell_id", "c001", "coverage_score", 98.5)));

        mockMvc.perform(post(BASE_PATH + "/apiquery/{metadataId}", metadataId)
                        .header("X-DataGov-Subscription-Id", subscriptionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "select": ["cell_id", "coverage_score"],
                                  "filters": [
                                    {"field": "province", "op": "=", "value": "JS"}
                                  ],
                                  "limit": 10
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.queryId", notNullValue()))
                .andExpect(jsonPath("$.columns", hasSize(2)))
                .andExpect(jsonPath("$.rows[0].cell_id").value("c001"))
                .andExpect(jsonPath("$.rowCount").value(1));

        assertThat(executor.calls).hasSize(1);
        assertThat(executor.calls.get(0).sql())
                .isEqualTo("select `cell_id`, `coverage_score` from `default_catalog`.`ads`.`ads_cell_profile` where `province` = ? limit 10");
        Map<String, Object> record = jdbcTemplate.queryForMap("select * from query_record order by created_at desc limit 1");
        assertThat(record.get("SUBSCRIPTION_ID")).isEqualTo(subscriptionId);
        assertThat(record.get("REQUEST_TYPE")).isEqualTo("PRODUCT_API");
    }

    @Test
    void formalSqlQueryUsesExistingSqlGateway() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/sqlquery")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sql": "select cell_id from ads_cell_profile",
                                  "limit": 5,
                                  "subscriptionId": "%s"
                                }
                                """.formatted(subscriptionId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.queryId", notNullValue()));

        assertThat(executor.calls).hasSize(1);
        assertThat(executor.calls.get(0).sql())
                .isEqualTo("select cell_id from `default_catalog`.`ads`.`ads_cell_profile` limit 5");
        Map<String, Object> record = jdbcTemplate.queryForMap("select * from query_record order by created_at desc limit 1");
        assertThat(record.get("REQUEST_TYPE")).isEqualTo("SQL_GATEWAY");
        assertThat(record.get("SUBSCRIPTION_ID")).isEqualTo(subscriptionId);
    }

    @Test
    void formalApiQueryMissingMetadataReturns404() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/apiquery/{metadataId}", "missing_metadata")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "select": ["cell_id"]
                                }
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
    }

    @TestConfiguration
    static class FormalQueryTestConfig {
        @Bean
        @Primary
        FakeStarRocksQueryExecutor fakeStarRocksQueryExecutor() {
            return new FakeStarRocksQueryExecutor();
        }
    }

    static class FakeStarRocksQueryExecutor implements StarRocksQueryExecutor {
        private QueryResult result = new QueryResult(List.of("cell_id"), List.of(Map.of("cell_id", "c001")));
        private final List<Call> calls = new ArrayList<>();

        @Override
        public QueryResult execute(String sql, List<Object> params, int maxRows, Duration timeout) {
            calls.add(new Call(sql, List.copyOf(params), maxRows, timeout));
            return result;
        }
    }

    record Call(String sql, List<Object> params, int maxRows, Duration timeout) {
    }
}
```

- [x] **Step 2: Run the formal query test and confirm it fails**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=FormalQueryControllerTest test
```

Expected: fails with missing formal query route.

- [x] **Step 3: Add the formal query controller**

Create `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/query/FormalQueryController.java`:

```java
package io.datagov.server.query;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.QueryDtos;
import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.asset.AssetRepository;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/rest/oss/inner/modelengineservice/v1")
public class FormalQueryController {
    private static final String SUBSCRIPTION_HEADER = "X-DataGov-Subscription-Id";

    private final AssetRepository assetRepository;
    private final ProductQueryService productQueryService;
    private final SqlGatewayService sqlGatewayService;

    public FormalQueryController(
            AssetRepository assetRepository,
            ProductQueryService productQueryService,
            SqlGatewayService sqlGatewayService
    ) {
        this.assetRepository = assetRepository;
        this.productQueryService = productQueryService;
        this.sqlGatewayService = sqlGatewayService;
    }

    @PostMapping("/apiquery/{metadataId}")
    public QueryDtos.QueryResponse queryMetadata(
            @PathVariable("metadataId") String metadataId,
            @RequestHeader(name = SUBSCRIPTION_HEADER, required = false) String subscriptionId,
            @Valid @RequestBody(required = false) QueryDtos.AssetQueryRequest request
    ) {
        AssetDtos.AssetResponse asset = assetRepository.findAssetById(metadataId)
                .orElseThrow(() -> new AssetNotFoundException(metadataId));
        return productQueryService.query(asset.assetCode(), withHeaderSubscriptionId(request, subscriptionId));
    }

    @PostMapping("/sqlquery")
    public QueryDtos.QueryResponse querySql(@Valid @RequestBody QueryDtos.SqlQueryRequest request) {
        return sqlGatewayService.query(request);
    }

    private QueryDtos.AssetQueryRequest withHeaderSubscriptionId(
            QueryDtos.AssetQueryRequest request,
            String subscriptionId
    ) {
        if (subscriptionId == null || subscriptionId.isBlank()) {
            return request;
        }
        if (request == null) {
            return new QueryDtos.AssetQueryRequest(null, null, null, subscriptionId, null, null);
        }
        if (request.subscriptionId() != null && !request.subscriptionId().isBlank()) {
            return request;
        }
        return new QueryDtos.AssetQueryRequest(
                request.select(),
                request.filters(),
                request.limit(),
                subscriptionId,
                request.consumerName(),
                request.environment());
    }
}
```

- [x] **Step 4: Run formal and legacy query tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=FormalQueryControllerTest,QueryControllerTest test
```

Expected: `BUILD SUCCESS`.

- [x] **Step 5: Commit formal query routes**

Commit:

```powershell
git add data-gov-platform/data-gov-server/src/main/java/io/datagov/server/query/FormalQueryController.java `
        data-gov-platform/data-gov-server/src/test/java/io/datagov/server/query/FormalQueryControllerTest.java
git commit -m "Add formal query API"
```

## Task 5: Full Verification And Push Prep

**Files:**
- Verify all touched files.
- No Docker Compose files should change in this phase.

- [x] **Step 1: Run the full Maven test suite**

Run:

```powershell
cd data-gov-platform
mvn test
```

Expected: `BUILD SUCCESS`. This validates server, common, and SDK modules together.

- [x] **Step 2: Check whitespace and compose drift**

Run:

```powershell
git diff --check
git status --short -- app-compose.yml docker-compose.yml compose.yaml data-gov-platform\app-compose.yml
```

Expected: `git diff --check` prints no issues. The compose status command prints no changed compose file for this phase.

- [x] **Step 3: Inspect all work**

Run:

```powershell
git status -sb
git log --oneline -5
```

Expected: branch is `master`, local commits are ahead of `origin/master` until pushed, and the last commits are the formal subscription/query commits from this plan.

- [x] **Step 4: Push coordination**

Push is handled by the current coordinating agent after final verification.

## Self-Review

- Spec coverage: Formal subscription create/list/cancel and formal product API/SQL query paths are covered by Tasks 1 through 4. Query record persistence stays in existing services and is covered by formal query tests.
- Type consistency: `metadataId` maps to `data_asset.asset_id` through `AssetRepository.findAssetById(...)`. Formal subscription responses use `fields` while legacy responses keep `declaredFields`.
- Backward compatibility: Legacy status values remain in `SubscriptionStatus`; legacy `/api` tests are run after service changes.
- Infrastructure: No compose files are changed. The shared infrastructure rule does not require compose config validation for this phase because no Docker Compose infrastructure is modified.
