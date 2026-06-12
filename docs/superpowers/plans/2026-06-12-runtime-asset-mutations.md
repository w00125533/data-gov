# Runtime Asset Mutations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add runtime asset update and unregister APIs that persist metadata changes and emit subscription notifications through the existing asset event pipeline.

**Architecture:** Extend the current `/api/assets` Spring MVC surface instead of introducing the formal `/metadata` path in this slice. `data-gov-common` owns new request/response DTOs, `data-gov-server` owns runtime mutation orchestration, and the existing `EventService` continues to own event persistence, subscription matching, and Kafka notification delivery.

**Tech Stack:** Java 17, Spring Boot 3.3, JDBC/JdbcTemplate, H2 tests, MockMvc, Mockito, Spring Kafka mock publisher.

---

## Completion Status

Completed and verified on 2026-06-12:

- `cd data-gov-platform; mvn test` -> `BUILD SUCCESS`; server 43 tests passed, SDK 15 tests passed.
- `git diff --check` -> exit 0, no whitespace errors; Git emitted CRLF conversion warnings only.
- `git status --short -- app-compose.yml docker-compose.yml compose.yaml data-gov-platform\app-compose.yml` -> no infrastructure file changes.
- `git status --short` -> implementation changes are limited to common DTOs, asset controller/service, runtime mutation test, and plan documentation.

## Scope

Build this phase:

- `PATCH /api/assets/{assetCode}` for runtime metadata updates.
- `DELETE /api/assets/{assetCode}` for runtime unregister by soft-offlining an asset.
- Runtime mutation responses containing both the changed asset detail and emitted event notification result.
- Default `SCHEMA_CHANGE` notification for runtime updates unless the request supplies a different `eventType`.
- `OFFLINE` notification for runtime unregister.
- Tests proving update notification delivery, unregister notification delivery, and missing asset behavior.

Do not build this phase:

- Formal `/rest/oss/inner/modelengineservice/v1/metadata` path migration.
- Startup snapshot sync semantics.
- New database tables or Flyway migrations.
- Notification pull/ack APIs.
- Drift analysis.
- Frontend UI.
- Docker Compose or shared infrastructure changes.

## Existing Context

Current relevant files:

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/AssetDtos.java`
- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/AssetEventType.java`
- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LifecycleStatus.java`
- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetController.java`
- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetService.java`
- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetRepository.java`
- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/event/EventService.java`
- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/event/NotificationPublisher.java`
- `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/asset/AssetControllerTest.java`
- `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/event/EventControllerTest.java`

Existing behaviors to preserve:

- `POST /api/assets/register` remains the upsert registration endpoint and does not emit runtime notifications in this slice.
- Kafka assets remain non-queryable even if the request asks for `queryable=true`.
- `AssetService.register` continues to increment `schemaVersion` for repeated registration.
- Event notification matching still uses active subscriptions and `notify_on` JSON text matching.

## API Contract

### PATCH `/api/assets/{assetCode}`

Request:

```json
{
  "assetName": "ADS Cell Profile V2",
  "description": "Runtime updated profile table",
  "fields": [
    {
      "fieldName": "cell_id",
      "fieldType": "varchar",
      "ordinalPosition": 1,
      "nullable": false,
      "primaryKey": true
    },
    {
      "fieldName": "coverage_score",
      "fieldType": "double",
      "ordinalPosition": 2,
      "nullable": true
    }
  ],
  "eventType": "SCHEMA_CHANGE",
  "severity": "WARN"
}
```

Response:

```json
{
  "asset": {
    "asset": {
      "assetCode": "ads_cell_profile",
      "assetName": "ADS Cell Profile V2",
      "schemaVersion": 2,
      "lifecycleStatus": "ACTIVE"
    },
    "fields": [
      {"fieldName": "cell_id"},
      {"fieldName": "coverage_score"}
    ],
    "binding": null
  },
  "event": {
    "event": {
      "assetCode": "ads_cell_profile",
      "eventType": "SCHEMA_CHANGE",
      "severity": "WARN"
    },
    "notifications": [
      {
        "consumerName": "rno-dashboard",
        "status": "SENT"
      }
    ]
  }
}
```

### DELETE `/api/assets/{assetCode}`

Request:

```json
{
  "reason": "dataset retired",
  "operator": "network-team"
}
```

Response:

```json
{
  "asset": {
    "asset": {
      "assetCode": "ads_cell_profile",
      "lifecycleStatus": "OFFLINE",
      "queryable": false,
      "federatedQueryable": false
    }
  },
  "event": {
    "event": {
      "eventType": "OFFLINE",
      "severity": "WARN"
    }
  }
}
```

## File Structure

- Modify: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/AssetDtos.java`
  - Add runtime mutation request/response records.
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetController.java`
  - Add `PATCH` and `DELETE` mappings.
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetService.java`
  - Add runtime update and unregister orchestration.
  - Inject existing `EventService`.
  - Emit asset events after the asset mutation transaction commits.
- Test: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/asset/AssetRuntimeMutationControllerTest.java`
  - New focused MockMvc coverage for runtime mutation behavior.

No repository changes are required for this slice because `AssetRepository` already supports finding, updating, replacing fields, and replacing active binding records.

## Task 1: Runtime Mutation DTOs And Failing Controller Tests

**Files:**

- Modify: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/AssetDtos.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/asset/AssetRuntimeMutationControllerTest.java`

- [x] **Step 1: Add DTO records to the common module**

Add these imports to `AssetDtos.java`:

```java
import io.datagov.common.enums.AssetEventType;
```

Add these records inside `AssetDtos` after `RegisterAssetRequest`:

```java
    public record UpdateAssetRequest(
            String assetName,
            AssetType assetType,
            AssetEngine engine,
            String domain,
            String owner,
            String description,
            LifecycleStatus lifecycleStatus,
            Boolean queryable,
            Boolean federatedQueryable,
            @Valid List<FieldRequest> fields,
            @Valid PhysicalBindingRequest physicalBinding,
            AssetEventType eventType,
            String severity
    ) {
    }

    public record UnregisterAssetRequest(
            @NotBlank String reason,
            String operator
    ) {
    }
```

Add this record after `AssetDetailResponse`:

```java
    public record AssetMutationResponse(
            AssetDetailResponse asset,
            EventDtos.CreateAssetEventResponse event
    ) {
    }
```

- [x] **Step 2: Write failing runtime mutation controller tests**

Create `AssetRuntimeMutationControllerTest.java`:

```java
package io.datagov.server.asset;

import io.datagov.common.dto.EventDtos;
import io.datagov.common.enums.AssetEventType;
import io.datagov.server.event.NotificationPublisher;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentCaptor.forClass;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class AssetRuntimeMutationControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @MockBean
    private NotificationPublisher notificationPublisher;

    @Test
    void patchAssetUpdatesMetadataAndEmitsSchemaChangeNotification() throws Exception {
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"),
                any(EventDtos.NotificationMessage.class)))
                .thenReturn(CompletableFuture.completedFuture(null));
        registerTableAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard", "SCHEMA_CHANGE");

        mockMvc.perform(patch("/api/assets/ads_cell_profile")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetName": "ADS Cell Profile V2",
                                  "description": "Runtime updated profile table",
                                  "fields": [
                                    {
                                      "fieldName": "cell_id",
                                      "fieldType": "varchar",
                                      "ordinalPosition": 1,
                                      "nullable": false,
                                      "primaryKey": true
                                    },
                                    {
                                      "fieldName": "coverage_score",
                                      "fieldType": "double",
                                      "ordinalPosition": 2,
                                      "nullable": true
                                    }
                                  ],
                                  "severity": "WARN"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.asset.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.asset.asset.assetName").value("ADS Cell Profile V2"))
                .andExpect(jsonPath("$.asset.asset.schemaVersion").value(2))
                .andExpect(jsonPath("$.asset.fields", hasSize(2)))
                .andExpect(jsonPath("$.asset.fields[1].fieldName").value("coverage_score"))
                .andExpect(jsonPath("$.event.event.eventType").value("SCHEMA_CHANGE"))
                .andExpect(jsonPath("$.event.event.severity").value("WARN"))
                .andExpect(jsonPath("$.event.notifications", hasSize(1)))
                .andExpect(jsonPath("$.event.notifications[0].status").value("SENT"));

        Integer eventCount = jdbcTemplate.queryForObject(
                "select count(*) from asset_event where event_type = 'SCHEMA_CHANGE'",
                Integer.class);
        Integer notificationCount = jdbcTemplate.queryForObject(
                "select count(*) from subscription_notification where status = 'SENT'",
                Integer.class);
        assertThat(eventCount).isEqualTo(1);
        assertThat(notificationCount).isEqualTo(1);

        ArgumentCaptor<EventDtos.NotificationMessage> messageCaptor =
                forClass(EventDtos.NotificationMessage.class);
        verify(notificationPublisher, times(1))
                .publish(eq("data-gov.subscription-notifications"), messageCaptor.capture());
        EventDtos.NotificationMessage message = messageCaptor.getValue();
        assertThat(message.assetCode()).isEqualTo("ads_cell_profile");
        assertThat(message.eventType()).isEqualTo(AssetEventType.SCHEMA_CHANGE);
        assertThat(message.payload()).containsEntry("operation", "PATCH_ASSET");
        assertThat(message.payload()).containsEntry("changedSections", List.of("asset", "fields"));
    }

    @Test
    void deleteAssetMarksOfflineAndEmitsOfflineNotification() throws Exception {
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"),
                any(EventDtos.NotificationMessage.class)))
                .thenReturn(CompletableFuture.completedFuture(null));
        registerTableAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard", "OFFLINE");

        mockMvc.perform(delete("/api/assets/ads_cell_profile")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "reason": "dataset retired",
                                  "operator": "network-team"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.asset.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.asset.asset.lifecycleStatus").value("OFFLINE"))
                .andExpect(jsonPath("$.asset.asset.queryable").value(false))
                .andExpect(jsonPath("$.asset.asset.federatedQueryable").value(false))
                .andExpect(jsonPath("$.event.event.eventType").value("OFFLINE"))
                .andExpect(jsonPath("$.event.event.severity").value("WARN"))
                .andExpect(jsonPath("$.event.notifications", hasSize(1)))
                .andExpect(jsonPath("$.event.notifications[0].consumerName").value("rno-dashboard"));

        mockMvc.perform(get("/api/assets/ads_cell_profile"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.lifecycleStatus").value("OFFLINE"))
                .andExpect(jsonPath("$.asset.queryable").value(false));

        ArgumentCaptor<EventDtos.NotificationMessage> messageCaptor =
                forClass(EventDtos.NotificationMessage.class);
        verify(notificationPublisher, times(1))
                .publish(eq("data-gov.subscription-notifications"), messageCaptor.capture());
        EventDtos.NotificationMessage message = messageCaptor.getValue();
        assertThat(message.eventType()).isEqualTo(AssetEventType.OFFLINE);
        assertThat(message.payload()).containsEntry("operation", "DELETE_ASSET");
        assertThat(message.payload()).containsEntry("reason", "dataset retired");
        assertThat(message.payload()).containsEntry("operator", "network-team");
    }

    @Test
    void patchUnknownAssetReturns404() throws Exception {
        mockMvc.perform(patch("/api/assets/missing_asset")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetName": "Missing"
                                }
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
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
                                  "domain": "wireless",
                                  "owner": "network-team",
                                  "lifecycleStatus": "ACTIVE",
                                  "queryable": true,
                                  "federatedQueryable": true,
                                  "fields": [
                                    {
                                      "fieldName": "cell_id",
                                      "fieldType": "varchar",
                                      "ordinalPosition": 1,
                                      "nullable": false,
                                      "primaryKey": true
                                    }
                                  ]
                                }
                                """.formatted(assetCode, assetCode)))
                .andExpect(status().isOk());
    }

    private void createSubscription(String assetCode, String consumerName, String notifyOn) throws Exception {
        mockMvc.perform(post("/api/assets/{assetCode}/subscriptions", assetCode)
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
                .andExpect(status().isOk());
    }
}
```

- [x] **Step 3: Run tests and verify red**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=AssetRuntimeMutationControllerTest test
```

Expected: compilation fails because `PATCH /api/assets/{assetCode}`, `DELETE /api/assets/{assetCode}`, and `AssetDtos.AssetMutationResponse` are not implemented.

## Task 2: Runtime Update API

**Files:**

- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetController.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetService.java`

- [x] **Step 1: Add the PATCH mapping**

Add imports to `AssetController.java`:

```java
import org.springframework.web.bind.annotation.PatchMapping;
```

Add this method after `register`:

```java
    @PatchMapping("/{assetCode}")
    public AssetDtos.AssetMutationResponse updateAsset(
            @PathVariable("assetCode") String assetCode,
            @Valid @RequestBody AssetDtos.UpdateAssetRequest request
    ) {
        return assetService.updateRuntime(assetCode, request);
    }
```

- [x] **Step 2: Inject EventService into AssetService**

Add import:

```java
import io.datagov.common.dto.EventDtos;
import io.datagov.common.enums.AssetEventType;
import io.datagov.server.event.EventService;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.Map;
```

Change fields and constructor:

```java
    private final AssetRepository assetRepository;
    private final TransactionTemplate transactionTemplate;
    private final EventService eventService;

    public AssetService(
            AssetRepository assetRepository,
            TransactionTemplate transactionTemplate,
            EventService eventService
    ) {
        this.assetRepository = assetRepository;
        this.transactionTemplate = transactionTemplate;
        this.eventService = eventService;
    }
```

- [x] **Step 3: Add update orchestration methods**

Add these methods to `AssetService` before `listAssets`:

```java
    public AssetDtos.AssetMutationResponse updateRuntime(
            String assetCode,
            AssetDtos.UpdateAssetRequest request
    ) {
        AssetDtos.AssetDetailResponse detail =
                transactionTemplate.execute(status -> updateRuntimeInTransaction(assetCode, request));
        EventDtos.CreateAssetEventResponse event = eventService.createEvent(
                assetCode,
                new EventDtos.CreateAssetEventRequest(
                        request.eventType() == null ? AssetEventType.SCHEMA_CHANGE : request.eventType(),
                        request.severity(),
                        updatePayload(detail.asset(), request)));
        return new AssetDtos.AssetMutationResponse(detail, event);
    }

    private AssetDtos.AssetDetailResponse updateRuntimeInTransaction(
            String assetCode,
            AssetDtos.UpdateAssetRequest request
    ) {
        AssetDtos.AssetResponse existing = requireAsset(assetCode);
        AssetEngine engine = request.engine() == null ? existing.engine() : request.engine();
        boolean kafkaAsset = engine == AssetEngine.KAFKA;
        boolean queryable = !kafkaAsset && (
                request.queryable() == null ? existing.queryable() : Boolean.TRUE.equals(request.queryable()));
        boolean federatedQueryable = !kafkaAsset && (
                request.federatedQueryable() == null
                        ? existing.federatedQueryable()
                        : Boolean.TRUE.equals(request.federatedQueryable()));
        Instant now = Instant.now();

        AssetDtos.AssetResponse updated = new AssetDtos.AssetResponse(
                existing.assetId(),
                existing.assetCode(),
                request.assetName() == null ? existing.assetName() : request.assetName(),
                request.assetType() == null ? existing.assetType() : request.assetType(),
                engine,
                request.domain() == null ? existing.domain() : request.domain(),
                request.owner() == null ? existing.owner() : request.owner(),
                request.description() == null ? existing.description() : request.description(),
                request.lifecycleStatus() == null ? existing.lifecycleStatus() : request.lifecycleStatus(),
                existing.schemaVersion() + 1,
                queryable,
                federatedQueryable,
                existing.createdAt(),
                now);

        assetRepository.updateAsset(updated);
        if (request.fields() != null) {
            assetRepository.replaceFields(updated.assetId(), toFieldResponses(updated.assetId(), request.fields()));
        }
        if (request.physicalBinding() != null) {
            assetRepository.replaceBinding(
                    updated.assetId(),
                    toBindingResponse(updated.assetId(), request.physicalBinding()));
        }

        return new AssetDtos.AssetDetailResponse(
                updated,
                assetRepository.findFields(updated.assetId()),
                assetRepository.findActiveBinding(updated.assetId()).orElse(null));
    }

    private Map<String, Object> updatePayload(
            AssetDtos.AssetResponse asset,
            AssetDtos.UpdateAssetRequest request
    ) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("operation", "PATCH_ASSET");
        payload.put("assetCode", asset.assetCode());
        payload.put("schemaVersion", asset.schemaVersion());
        payload.put("changedSections", changedSections(request));
        return Map.copyOf(payload);
    }

    private List<String> changedSections(AssetDtos.UpdateAssetRequest request) {
        List<String> sections = new ArrayList<>();
        if (request.assetName() != null
                || request.assetType() != null
                || request.engine() != null
                || request.domain() != null
                || request.owner() != null
                || request.description() != null
                || request.lifecycleStatus() != null
                || request.queryable() != null
                || request.federatedQueryable() != null) {
            sections.add("asset");
        }
        if (request.fields() != null) {
            sections.add("fields");
        }
        if (request.physicalBinding() != null) {
            sections.add("binding");
        }
        if (sections.isEmpty()) {
            sections.add("asset");
        }
        return List.copyOf(sections);
    }
```

- [x] **Step 4: Run the focused update test**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=AssetRuntimeMutationControllerTest#patchAssetUpdatesMetadataAndEmitsSchemaChangeNotification test
```

Expected: `BUILD SUCCESS` for the update test.

## Task 3: Runtime Unregister API

**Files:**

- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetController.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetService.java`

- [x] **Step 1: Add the DELETE mapping**

Add import to `AssetController.java`:

```java
import org.springframework.web.bind.annotation.DeleteMapping;
```

Add this method after `updateAsset`:

```java
    @DeleteMapping("/{assetCode}")
    public AssetDtos.AssetMutationResponse unregisterAsset(
            @PathVariable("assetCode") String assetCode,
            @Valid @RequestBody AssetDtos.UnregisterAssetRequest request
    ) {
        return assetService.unregisterRuntime(assetCode, request);
    }
```

- [x] **Step 2: Add unregister orchestration methods**

Add these methods to `AssetService` after `updateRuntimeInTransaction`:

```java
    public AssetDtos.AssetMutationResponse unregisterRuntime(
            String assetCode,
            AssetDtos.UnregisterAssetRequest request
    ) {
        AssetDtos.AssetDetailResponse detail =
                transactionTemplate.execute(status -> unregisterRuntimeInTransaction(assetCode));
        EventDtos.CreateAssetEventResponse event = eventService.createEvent(
                assetCode,
                new EventDtos.CreateAssetEventRequest(
                        AssetEventType.OFFLINE,
                        "WARN",
                        unregisterPayload(detail.asset(), request)));
        return new AssetDtos.AssetMutationResponse(detail, event);
    }

    private AssetDtos.AssetDetailResponse unregisterRuntimeInTransaction(String assetCode) {
        AssetDtos.AssetResponse existing = requireAsset(assetCode);
        Instant now = Instant.now();
        AssetDtos.AssetResponse offline = new AssetDtos.AssetResponse(
                existing.assetId(),
                existing.assetCode(),
                existing.assetName(),
                existing.assetType(),
                existing.engine(),
                existing.domain(),
                existing.owner(),
                existing.description(),
                LifecycleStatus.OFFLINE,
                existing.schemaVersion() + 1,
                false,
                false,
                existing.createdAt(),
                now);
        assetRepository.updateAsset(offline);
        return new AssetDtos.AssetDetailResponse(
                offline,
                assetRepository.findFields(offline.assetId()),
                assetRepository.findActiveBinding(offline.assetId()).orElse(null));
    }

    private Map<String, Object> unregisterPayload(
            AssetDtos.AssetResponse asset,
            AssetDtos.UnregisterAssetRequest request
    ) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("operation", "DELETE_ASSET");
        payload.put("assetCode", asset.assetCode());
        payload.put("schemaVersion", asset.schemaVersion());
        payload.put("reason", request.reason());
        if (request.operator() != null && !request.operator().isBlank()) {
            payload.put("operator", request.operator());
        }
        return Map.copyOf(payload);
    }
```

- [x] **Step 3: Run all runtime mutation tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=AssetRuntimeMutationControllerTest test
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

Expected: no output.

- [x] **Step 3: Confirm no infrastructure files changed**

Run:

```powershell
git status --short -- app-compose.yml docker-compose.yml compose.yaml data-gov-platform\app-compose.yml
```

Expected: no output.

- [x] **Step 4: Inspect changed files**

Run:

```powershell
git status --short
```

Expected changed files are limited to the common DTO, asset controller/service, and the new runtime mutation test unless the executor also updates this plan status.

## Review Checklist

Before merge:

- `PATCH /api/assets/{assetCode}` updates existing asset metadata, fields, and binding only for request sections that are present.
- Runtime update increments `schemaVersion`.
- Runtime update emits an `asset_event` with default `SCHEMA_CHANGE`.
- Runtime update publishes notifications only to active subscriptions whose `notify_on` contains the emitted event type.
- `DELETE /api/assets/{assetCode}` soft-offlines the asset using `LifecycleStatus.OFFLINE`.
- Runtime unregister disables `queryable` and `federatedQueryable`.
- Runtime unregister emits an `OFFLINE` notification.
- Missing assets keep returning `ASSET_NOT_FOUND`.
- `POST /api/assets/register` behavior is unchanged.
- No Docker Compose files are changed.

## Plan Self-Review

Spec coverage:

- Runtime metadata modification: Tasks 1 and 2.
- Runtime unregister: Tasks 1 and 3.
- Notification on metadata change: Tasks 2 and 3 reuse `EventService`.
- No notification pull/ack API: no task adds these endpoints.
- No drift analysis: no task adds drift tables, DTOs, services, or endpoints.
- No infrastructure changes: Task 4 checks compose files explicitly.

Placeholder scan:

- Clean.

Type consistency:

- `AssetDtos.AssetMutationResponse` wraps `AssetDtos.AssetDetailResponse` and `EventDtos.CreateAssetEventResponse`.
- `AssetEventType.SCHEMA_CHANGE` and `AssetEventType.OFFLINE` already exist.
- `LifecycleStatus.OFFLINE` already exists.
- `EventService.createEvent` is reused without changing notification matching semantics.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-12-runtime-asset-mutations.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.
