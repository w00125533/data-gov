# Formal Metadata Snapshot API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first formal `/rest/oss/inner/modelengineservice/v1/metadata` API slice for full metadata snapshot registration, metadata discovery, and runtime mutation by `metadataId`.

**Architecture:** Keep existing `/api/...` routes stable and add a formal metadata facade that reuses the current asset repository/service patterns. Persist producer scope and per-item declaration hashes on `data_asset` so startup snapshots can create, update, leave unchanged, or soft-remove scoped metadata idempotently. The SDK will call the formal metadata snapshot endpoint for metadata declarations while existing subscription and query APIs continue unchanged in this slice.

**Tech Stack:** Java 17, Spring Boot 3.3, JDBC/JdbcTemplate, Flyway, H2 tests, MockMvc, Spring Boot SDK autoconfiguration.

---

## Scope

Build this phase:

- `POST /rest/oss/inner/modelengineservice/v1/metadata/register` for microservice-scoped full metadata snapshots.
- `GET /rest/oss/inner/modelengineservice/v1/metadata` for metadata list discovery.
- `GET /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}` for detail discovery.
- `PATCH /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}` for runtime updates by metadata ID.
- `DELETE /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}` for runtime unregister by metadata ID.
- SDK startup metadata declaration properties and client call to the formal register endpoint.
- Tests proving created, updated, unchanged, removed-by-snapshot, discovery, runtime mutation, and SDK request assembly behavior.

Do not build this phase:

- Formal subscription paths.
- Formal `apiquery` and `sqlquery` paths.
- Notification pull or ack APIs.
- Drift remediation APIs.
- Frontend UI.
- Docker Compose or shared infrastructure changes.
- Duplicate `assetCode` values across different producer scopes. Existing global `data_asset.asset_code` uniqueness remains in force.

## Existing Context

Current implemented routes:

- `POST /api/assets/register`
- `GET /api/assets`
- `GET /api/assets/{assetCode}`
- `PATCH /api/assets/{assetCode}`
- `DELETE /api/assets/{assetCode}`
- `GET /api/assets/{assetCode}/lineage`
- `POST /api/assets/{assetCode}/query`
- `POST /api/sql`
- `POST /api/sdk/subscriptions/register`

Current core files:

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/AssetDtos.java`
- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LifecycleStatus.java`
- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetRepository.java`
- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetService.java`
- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetController.java`
- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`
- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DataGovClient.java`
- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DefaultDataGovClient.java`
- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovProperties.java`
- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovStartupRegistrar.java`

## API Contract

### POST `/rest/oss/inner/modelengineservice/v1/metadata/register`

Request:

```json
{
  "producer": {
    "serviceName": "rno-profile-service",
    "serviceType": "MICROSERVICE",
    "owner": "network-team",
    "environment": "prod",
    "instanceId": "pod-rno-profile-7d8f"
  },
  "syncMode": "FULL",
  "metadataList": [
    {
      "assetCode": "ads_cell_profile",
      "assetName": "ADS Cell Profile",
      "metadataType": "TABLE",
      "sourceType": "STARROCKS",
      "domain": "wireless-rno",
      "owner": "network-team",
      "description": "Cell profile table",
      "queryable": true,
      "federatedQueryable": true,
      "schema": [
        {
          "fieldName": "cell_id",
          "fieldType": "varchar",
          "ordinal": 1,
          "nullable": false,
          "primaryKey": true
        }
      ],
      "binding": {
        "sourceType": "STARROCKS",
        "catalog": "default_catalog",
        "database": "ads",
        "table": "ads_cell_profile"
      }
    }
  ]
}
```

Response:

```json
{
  "syncScope": {
    "serviceName": "rno-profile-service",
    "environment": "prod"
  },
  "createdCount": 1,
  "updatedCount": 0,
  "unchangedCount": 0,
  "removedBySnapshotCount": 0,
  "items": [
    {
      "metadataId": "asset_abc",
      "assetCode": "ads_cell_profile",
      "status": "CREATED"
    }
  ],
  "syncedAt": "2026-06-13T00:00:00Z"
}
```

### GET `/rest/oss/inner/modelengineservice/v1/metadata`

Supports `keyword`, `domain`, `metadataType`, `owner`, `page`, and `size`. This slice filters in Java over the existing ordered asset list and caps `size` to `1..100`.

### GET `/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}`

Uses the current `asset_id` as `metadataId`.

### PATCH and DELETE `/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}`

Resolve `metadataId` to `assetCode`, then reuse `AssetService.updateRuntime` and `AssetService.unregisterRuntime`.

## Data Model

Add migration:

- `data-gov-platform/data-gov-server/src/main/resources/db/migration/V7__metadata_snapshot_scope.sql`

Migration SQL:

```sql
alter table data_asset add column producer_service_name varchar(128);
alter table data_asset add column producer_service_type varchar(32);
alter table data_asset add column producer_environment varchar(64);
alter table data_asset add column producer_owner varchar(128);
alter table data_asset add column declaration_hash varchar(128);
alter table data_asset add column last_declared_instance_id varchar(256);
alter table data_asset add column last_synced_at timestamp;
alter table data_asset add column unregistered_at timestamp;

create index idx_data_asset_producer_scope
    on data_asset(producer_service_name, producer_environment);

create index idx_data_asset_last_synced_at on data_asset(last_synced_at);
```

`data_asset.asset_code` remains globally unique in this slice.

## File Structure

- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/MetadataProducerType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/MetadataSyncMode.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/MetadataSyncItemStatus.java`
- Modify: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LifecycleStatus.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/MetadataDtos.java`
- Create: `data-gov-platform/data-gov-server/src/main/resources/db/migration/V7__metadata_snapshot_scope.sql`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetRepository.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataController.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataService.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataDataAccessException.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`
- Modify: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DataGovClient.java`
- Modify: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DefaultDataGovClient.java`
- Modify: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovProperties.java`
- Modify: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovStartupRegistrar.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/metadata/MetadataSchemaMigrationTest.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/metadata/MetadataControllerTest.java`
- Create: `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/DefaultDataGovClientMetadataTest.java`
- Modify: `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/spring/DataGovAutoConfigurationTest.java`

## Task 1: Metadata Contracts And Migration

**Files:**

- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/MetadataProducerType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/MetadataSyncMode.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/MetadataSyncItemStatus.java`
- Modify: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LifecycleStatus.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/MetadataDtos.java`
- Create: `data-gov-platform/data-gov-server/src/main/resources/db/migration/V7__metadata_snapshot_scope.sql`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/metadata/MetadataSchemaMigrationTest.java`

- [ ] **Step 1: Write the failing schema and DTO test**

Create `MetadataSchemaMigrationTest.java`:

```java
package io.datagov.server.metadata;

import io.datagov.common.dto.MetadataDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LifecycleStatus;
import io.datagov.common.enums.MetadataProducerType;
import io.datagov.common.enums.MetadataSyncItemStatus;
import io.datagov.common.enums.MetadataSyncMode;
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
class MetadataSchemaMigrationTest {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void metadataSnapshotColumnsAndDtosAreAvailable() {
        Integer columnCount = jdbcTemplate.queryForObject("""
                select count(*)
                from information_schema.columns
                where table_name = 'DATA_ASSET'
                  and column_name in (
                      'PRODUCER_SERVICE_NAME',
                      'PRODUCER_SERVICE_TYPE',
                      'PRODUCER_ENVIRONMENT',
                      'DECLARATION_HASH',
                      'LAST_SYNCED_AT',
                      'UNREGISTERED_AT'
                  )
                """, Integer.class);

        MetadataDtos.MetadataSnapshotRegisterRequest request =
                new MetadataDtos.MetadataSnapshotRegisterRequest(
                        new MetadataDtos.ProducerRequest(
                                "rno-profile-service",
                                MetadataProducerType.MICROSERVICE,
                                "network-team",
                                "prod",
                                "pod-1"),
                        MetadataSyncMode.FULL,
                        List.of(new MetadataDtos.MetadataItemRequest(
                                "ads_cell_profile",
                                "ADS Cell Profile",
                                AssetType.TABLE,
                                AssetEngine.STARROCKS,
                                "wireless-rno",
                                "network-team",
                                "Cell profile table",
                                true,
                                true,
                                List.of(new MetadataDtos.MetadataFieldRequest(
                                        "cell_id",
                                        "varchar",
                                        1,
                                        false,
                                        false,
                                        true,
                                        false,
                                        "Cell id",
                                        null)),
                                new MetadataDtos.MetadataBindingRequest(
                                        AssetEngine.STARROCKS,
                                        "default_catalog",
                                        "ads",
                                        null,
                                        "ads_cell_profile",
                                        null,
                                        null,
                                        null,
                                        null,
                                        "starrocks",
                                        Map.of()),
                                null)));

        MetadataDtos.MetadataSyncResponse response = new MetadataDtos.MetadataSyncResponse(
                new MetadataDtos.MetadataSyncScope("rno-profile-service", "prod"),
                1,
                0,
                0,
                0,
                List.of(new MetadataDtos.MetadataSyncItemResponse(
                        "asset_1",
                        "ads_cell_profile",
                        MetadataSyncItemStatus.CREATED)),
                Instant.parse("2026-06-13T00:00:00Z"));

        assertThat(columnCount).isEqualTo(6);
        assertThat(request.producer().serviceName()).isEqualTo("rno-profile-service");
        assertThat(response.items().get(0).status()).isEqualTo(MetadataSyncItemStatus.CREATED);
        assertThat(LifecycleStatus.valueOf("REMOVED_BY_SNAPSHOT")).isEqualTo(LifecycleStatus.REMOVED_BY_SNAPSHOT);
    }
}
```

- [ ] **Step 2: Run the test and verify red**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=MetadataSchemaMigrationTest test
```

Expected: compilation fails because metadata DTOs, enums, lifecycle value, and V7 columns do not exist.

- [ ] **Step 3: Add metadata enums**

Create `MetadataProducerType.java`:

```java
package io.datagov.common.enums;

public enum MetadataProducerType {
    MICROSERVICE,
    FLINK,
    SPARK,
    MANUAL
}
```

Create `MetadataSyncMode.java`:

```java
package io.datagov.common.enums;

public enum MetadataSyncMode {
    FULL
}
```

Create `MetadataSyncItemStatus.java`:

```java
package io.datagov.common.enums;

public enum MetadataSyncItemStatus {
    CREATED,
    UPDATED,
    UNCHANGED,
    REMOVED_BY_SNAPSHOT
}
```

Modify `LifecycleStatus.java`:

```java
package io.datagov.common.enums;

public enum LifecycleStatus {
    DRAFT,
    ACTIVE,
    DEPRECATED,
    OFFLINE,
    REMOVED_BY_SNAPSHOT,
    UNREGISTERED
}
```

- [ ] **Step 4: Add metadata DTOs**

Create `MetadataDtos.java`:

```java
package io.datagov.common.dto;

import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.MetadataProducerType;
import io.datagov.common.enums.MetadataSyncItemStatus;
import io.datagov.common.enums.MetadataSyncMode;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class MetadataDtos {
    private MetadataDtos() {
    }

    public record ProducerRequest(
            @NotBlank String serviceName,
            @NotNull MetadataProducerType serviceType,
            String owner,
            @NotBlank String environment,
            String instanceId
    ) {
    }

    public record MetadataSnapshotRegisterRequest(
            @Valid @NotNull ProducerRequest producer,
            MetadataSyncMode syncMode,
            @Valid @NotEmpty List<MetadataItemRequest> metadataList
    ) {
    }

    public record MetadataItemRequest(
            @NotBlank String assetCode,
            String assetName,
            @NotNull AssetType metadataType,
            @NotNull AssetEngine sourceType,
            String domain,
            String owner,
            String description,
            Boolean queryable,
            Boolean federatedQueryable,
            @Valid List<MetadataFieldRequest> schema,
            @Valid MetadataBindingRequest binding,
            @Valid MetadataLineageRequest lineage
    ) {
    }

    public record MetadataFieldRequest(
            @NotBlank String fieldName,
            @NotBlank String fieldType,
            Integer ordinal,
            Boolean nullable,
            Boolean partitionKey,
            Boolean primaryKey,
            Boolean eventTime,
            String description,
            String expression
    ) {
    }

    public record MetadataBindingRequest(
            @NotNull AssetEngine sourceType,
            String catalog,
            String database,
            String schema,
            String table,
            String topic,
            String format,
            String locationUri,
            String connectionRef,
            String queryAdapter,
            Map<String, Object> properties
    ) {
    }

    public record MetadataLineageRequest(
            List<MetadataLineageEdgeRequest> upstreams,
            List<MetadataLineageEdgeRequest> downstreams
    ) {
    }

    public record MetadataLineageEdgeRequest(
            @NotBlank String assetCode,
            String expression,
            String processName,
            String jobName
    ) {
    }

    public record MetadataSyncScope(
            String serviceName,
            String environment
    ) {
    }

    public record MetadataSyncItemResponse(
            String metadataId,
            String assetCode,
            MetadataSyncItemStatus status
    ) {
    }

    public record MetadataSyncResponse(
            MetadataSyncScope syncScope,
            int createdCount,
            int updatedCount,
            int unchangedCount,
            int removedBySnapshotCount,
            List<MetadataSyncItemResponse> items,
            Instant syncedAt
    ) {
    }

    public record MetadataListResponse(
            List<MetadataSummaryResponse> items,
            int page,
            int size,
            int total
    ) {
    }

    public record MetadataSummaryResponse(
            String metadataId,
            String assetCode,
            String assetName,
            AssetType metadataType,
            AssetEngine sourceType,
            String domain,
            String owner,
            boolean queryable
    ) {
    }

    public record MetadataDetailResponse(
            String metadataId,
            String assetCode,
            String assetName,
            AssetType metadataType,
            AssetEngine sourceType,
            String domain,
            String owner,
            String description,
            boolean queryable,
            boolean federatedQueryable,
            List<MetadataFieldResponse> schema,
            MetadataBindingResponse binding,
            Instant createdAt,
            Instant updatedAt
    ) {
    }

    public record MetadataFieldResponse(
            String fieldName,
            String fieldType,
            Integer ordinal,
            boolean nullable,
            boolean partitionKey,
            boolean primaryKey,
            boolean eventTime,
            String description,
            String expression
    ) {
    }

    public record MetadataBindingResponse(
            AssetEngine sourceType,
            String catalog,
            String database,
            String schema,
            String table,
            String topic,
            String qualifiedName,
            String format,
            String locationUri,
            String connectionRef,
            String queryAdapter,
            Map<String, Object> properties
    ) {
    }

    public record MetadataMutationResponse(
            String metadataId,
            String assetCode,
            String status,
            Instant changedAt
    ) {
    }
}
```

- [ ] **Step 5: Add V7 migration**

Create `V7__metadata_snapshot_scope.sql` using the SQL in the Data Model section.

- [ ] **Step 6: Run the focused schema test**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=MetadataSchemaMigrationTest test
```

Expected: `BUILD SUCCESS`.

## Task 2: Asset Repository Support For Metadata Scope

**Files:**

- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetRepository.java`

- [ ] **Step 1: Add repository test coverage through controller tests in Task 3**

No separate repository test is required in this task. Task 3 drives these methods through the public formal API.

- [ ] **Step 2: Add metadata lookup and scope methods**

Add imports:

```java
import io.datagov.common.enums.MetadataProducerType;
import org.springframework.dao.DataAccessException;
import java.util.Set;
```

Add methods to `AssetRepository`:

```java
public Optional<AssetDtos.AssetResponse> findAssetById(String assetId) {
    try {
        return Optional.ofNullable(jdbcTemplate.queryForObject("""
                select asset_id, asset_code, asset_name, asset_type, engine, domain, owner, description,
                       lifecycle_status, schema_version, queryable, federated_queryable, created_at, updated_at
                from data_asset
                where asset_id = ?
                """, assetMapper(), assetId));
    } catch (EmptyResultDataAccessException ex) {
        return Optional.empty();
    }
}

public String findDeclarationHash(String assetId) {
    try {
        return jdbcTemplate.queryForObject(
                "select declaration_hash from data_asset where asset_id = ?",
                String.class,
                assetId);
    } catch (EmptyResultDataAccessException ex) {
        return null;
    }
}

public void updateSnapshotScope(
        String assetId,
        String serviceName,
        MetadataProducerType serviceType,
        String environment,
        String owner,
        String declarationHash,
        String instanceId,
        Instant syncedAt
) {
    jdbcTemplate.update("""
            update data_asset
            set producer_service_name = ?,
                producer_service_type = ?,
                producer_environment = ?,
                producer_owner = ?,
                declaration_hash = ?,
                last_declared_instance_id = ?,
                last_synced_at = ?
            where asset_id = ?
            """,
            serviceName,
            serviceType.name(),
            environment,
            owner,
            declarationHash,
            instanceId,
            Timestamp.from(syncedAt),
            assetId);
}

public List<AssetDtos.AssetResponse> findAssetsInProducerScope(String serviceName, String environment) {
    return jdbcTemplate.query("""
            select asset_id, asset_code, asset_name, asset_type, engine, domain, owner, description,
                   lifecycle_status, schema_version, queryable, federated_queryable, created_at, updated_at
            from data_asset
            where producer_service_name = ? and producer_environment = ?
            order by asset_code
            """, assetMapper(), serviceName, environment);
}

public void markRemovedBySnapshot(String assetId, Instant removedAt) {
    jdbcTemplate.update("""
            update data_asset
            set lifecycle_status = ?,
                queryable = false,
                federated_queryable = false,
                updated_at = ?,
                last_synced_at = ?
            where asset_id = ?
            """,
            LifecycleStatus.REMOVED_BY_SNAPSHOT.name(),
            Timestamp.from(removedAt),
            Timestamp.from(removedAt),
            assetId);
}
```

- [ ] **Step 3: Run compile check**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -DskipTests compile
```

Expected: `BUILD SUCCESS`.

## Task 3: Formal Metadata Snapshot API

**Files:**

- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataDataAccessException.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataService.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataController.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/metadata/MetadataControllerTest.java`

- [ ] **Step 1: Write failing formal metadata API tests**

Create `MetadataControllerTest.java` with these tests:

```java
package io.datagov.server.metadata;

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
class MetadataControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void snapshotRegisterCreatesAndListsFormalMetadata() throws Exception {
        mockMvc.perform(post("/rest/oss/inner/modelengineservice/v1/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1))
                .andExpect(jsonPath("$.updatedCount").value(0))
                .andExpect(jsonPath("$.unchangedCount").value(0))
                .andExpect(jsonPath("$.removedBySnapshotCount").value(0))
                .andExpect(jsonPath("$.items[0].assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.items[0].status").value("CREATED"));

        String metadataId = metadataId("ads_cell_profile");

        mockMvc.perform(get("/rest/oss/inner/modelengineservice/v1/metadata")
                        .param("keyword", "cell")
                        .param("page", "1")
                        .param("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].metadataId").value(metadataId))
                .andExpect(jsonPath("$.items[0].metadataType").value("TABLE"))
                .andExpect(jsonPath("$.items[0].sourceType").value("STARROCKS"));

        mockMvc.perform(get("/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}", metadataId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.schema[0].fieldName").value("cell_id"))
                .andExpect(jsonPath("$.binding.qualifiedName").value("default_catalog.ads.ads_cell_profile"));
    }

    @Test
    void repeatedSnapshotReturnsUnchangedWithoutIncrementingSchemaVersion() throws Exception {
        mockMvc.perform(post("/rest/oss/inner/modelengineservice/v1/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1));

        Integer firstVersion = schemaVersion("ads_cell_profile");

        mockMvc.perform(post("/rest/oss/inner/modelengineservice/v1/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(0))
                .andExpect(jsonPath("$.updatedCount").value(0))
                .andExpect(jsonPath("$.unchangedCount").value(1))
                .andExpect(jsonPath("$.items[0].status").value("UNCHANGED"));

        org.assertj.core.api.Assertions.assertThat(schemaVersion("ads_cell_profile")).isEqualTo(firstVersion);
    }

    @Test
    void changedSnapshotUpdatesExistingMetadata() throws Exception {
        mockMvc.perform(post("/rest/oss/inner/modelengineservice/v1/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk());

        mockMvc.perform(post("/rest/oss/inner/modelengineservice/v1/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "producer": {
                                    "serviceName": "rno-profile-service",
                                    "serviceType": "MICROSERVICE",
                                    "owner": "network-team",
                                    "environment": "prod",
                                    "instanceId": "pod-2"
                                  },
                                  "syncMode": "FULL",
                                  "metadataList": [
                                    {
                                      "assetCode": "ads_cell_profile",
                                      "assetName": "ADS Cell Profile V2",
                                      "metadataType": "TABLE",
                                      "sourceType": "STARROCKS",
                                      "domain": "wireless-rno",
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
                                        "table": "ads_cell_profile"
                                      }
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(0))
                .andExpect(jsonPath("$.updatedCount").value(1))
                .andExpect(jsonPath("$.items[0].status").value("UPDATED"));

        String metadataId = metadataId("ads_cell_profile");
        mockMvc.perform(get("/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}", metadataId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.assetName").value("ADS Cell Profile V2"))
                .andExpect(jsonPath("$.schema", hasSize(2)));
    }

    @Test
    void fullSnapshotMarksMissingScopedMetadataRemovedBySnapshot() throws Exception {
        mockMvc.perform(post("/rest/oss/inner/modelengineservice/v1/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile", "ads_cell_quality")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(2));

        mockMvc.perform(post("/rest/oss/inner/modelengineservice/v1/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.removedBySnapshotCount").value(1))
                .andExpect(jsonPath("$.items[?(@.assetCode == 'ads_cell_quality')][0].status")
                        .value("REMOVED_BY_SNAPSHOT"));

        String removedId = metadataId("ads_cell_quality");
        mockMvc.perform(get("/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}", removedId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.assetCode").value("ads_cell_quality"))
                .andExpect(jsonPath("$.queryable").value(false));
    }

    @Test
    void patchAndDeleteMetadataByIdReuseRuntimeMutationBehavior() throws Exception {
        mockMvc.perform(post("/rest/oss/inner/modelengineservice/v1/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk());
        String metadataId = metadataId("ads_cell_profile");

        mockMvc.perform(patch("/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}", metadataId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetName": "ADS Cell Profile Runtime",
                                  "description": "Runtime metadata update"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.status").value("UPDATED"));

        mockMvc.perform(delete("/rest/oss/inner/modelengineservice/v1/metadata/{metadataId}", metadataId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "reason": "dataset retired",
                                  "operator": "network-team"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.status").value("UNREGISTERED"));
    }

    private String snapshotWithAssets(String... assetCodes) {
        String items = java.util.Arrays.stream(assetCodes)
                .map(assetCode -> """
                        {
                          "assetCode": "%s",
                          "assetName": "%s",
                          "metadataType": "TABLE",
                          "sourceType": "STARROCKS",
                          "domain": "wireless-rno",
                          "owner": "network-team",
                          "queryable": true,
                          "federatedQueryable": true,
                          "schema": [
                            {"fieldName": "cell_id", "fieldType": "varchar", "ordinal": 1, "nullable": false}
                          ],
                          "binding": {
                            "sourceType": "STARROCKS",
                            "catalog": "default_catalog",
                            "database": "ads",
                            "table": "%s",
                            "queryAdapter": "starrocks"
                          }
                        }
                        """.formatted(assetCode, assetCode, assetCode))
                .collect(java.util.stream.Collectors.joining(","));
        return """
                {
                  "producer": {
                    "serviceName": "rno-profile-service",
                    "serviceType": "MICROSERVICE",
                    "owner": "network-team",
                    "environment": "prod",
                    "instanceId": "pod-1"
                  },
                  "syncMode": "FULL",
                  "metadataList": [%s]
                }
                """.formatted(items);
    }

    private String metadataId(String assetCode) {
        return jdbcTemplate.queryForObject(
                "select asset_id from data_asset where asset_code = ?",
                String.class,
                assetCode);
    }

    private Integer schemaVersion(String assetCode) {
        return jdbcTemplate.queryForObject(
                "select schema_version from data_asset where asset_code = ?",
                Integer.class,
                assetCode);
    }
}
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=MetadataControllerTest test
```

Expected: fails because formal metadata controller and service do not exist.

- [ ] **Step 3: Add metadata exception and error mapping**

Create `MetadataDataAccessException.java`:

```java
package io.datagov.server.metadata;

public class MetadataDataAccessException extends RuntimeException {
    public MetadataDataAccessException(String message, Throwable cause) {
        super(message, cause);
    }
}
```

Modify `ApiExceptionHandler.java`:

```java
import io.datagov.server.metadata.MetadataDataAccessException;
```

Add handler:

```java
@ExceptionHandler(MetadataDataAccessException.class)
public ResponseEntity<Map<String, Object>> handleMetadataDataAccess(MetadataDataAccessException ex) {
    return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(Map.of(
                    "error", "METADATA_DATA_ACCESS_ERROR",
                    "message", ex.getMessage()));
}
```

- [ ] **Step 4: Implement metadata service**

Create `MetadataService.java`:

```java
package io.datagov.server.metadata;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.MetadataDtos;
import io.datagov.common.enums.LifecycleStatus;
import io.datagov.common.enums.MetadataSyncItemStatus;
import io.datagov.common.enums.MetadataSyncMode;
import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.asset.AssetRepository;
import io.datagov.server.asset.AssetService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;

@Service
public class MetadataService {
    private final AssetRepository assetRepository;
    private final AssetService assetService;
    private final TransactionTemplate transactionTemplate;
    private final ObjectMapper objectMapper;

    public MetadataService(
            AssetRepository assetRepository,
            AssetService assetService,
            TransactionTemplate transactionTemplate,
            ObjectMapper objectMapper
    ) {
        this.assetRepository = assetRepository;
        this.assetService = assetService;
        this.transactionTemplate = transactionTemplate;
        this.objectMapper = objectMapper;
    }

    public MetadataDtos.MetadataSyncResponse registerSnapshot(
            MetadataDtos.MetadataSnapshotRegisterRequest request
    ) {
        return transactionTemplate.execute(status -> registerSnapshotInTransaction(request));
    }

    private MetadataDtos.MetadataSyncResponse registerSnapshotInTransaction(
            MetadataDtos.MetadataSnapshotRegisterRequest request
    ) {
        MetadataDtos.ProducerRequest producer = request.producer();
        MetadataSyncMode syncMode = request.syncMode() == null ? MetadataSyncMode.FULL : request.syncMode();
        if (syncMode != MetadataSyncMode.FULL) {
            throw new IllegalArgumentException("Only FULL metadata sync is supported");
        }

        Instant syncedAt = Instant.now();
        List<MetadataDtos.MetadataSyncItemResponse> items = new ArrayList<>();
        int created = 0;
        int updated = 0;
        int unchanged = 0;

        for (MetadataDtos.MetadataItemRequest item : request.metadataList()) {
            String itemHash = declarationHash(item);
            AssetDtos.AssetResponse existing = assetRepository.findAssetByCode(item.assetCode()).orElse(null);
            MetadataSyncItemStatus itemStatus;
            AssetDtos.AssetResponse asset;
            if (existing == null) {
                asset = assetService.register(toRegisterRequest(item)).asset();
                itemStatus = MetadataSyncItemStatus.CREATED;
                created++;
            } else if (Objects.equals(assetRepository.findDeclarationHash(existing.assetId()), itemHash)) {
                asset = existing;
                itemStatus = MetadataSyncItemStatus.UNCHANGED;
                unchanged++;
            } else {
                asset = assetService.register(toRegisterRequest(item)).asset();
                itemStatus = MetadataSyncItemStatus.UPDATED;
                updated++;
            }

            assetRepository.updateSnapshotScope(
                    asset.assetId(),
                    producer.serviceName(),
                    producer.serviceType(),
                    producer.environment(),
                    producer.owner(),
                    itemHash,
                    producer.instanceId(),
                    syncedAt);
            items.add(new MetadataDtos.MetadataSyncItemResponse(asset.assetId(), asset.assetCode(), itemStatus));
        }

        int removed = 0;
        List<String> snapshotCodes = request.metadataList().stream()
                .map(MetadataDtos.MetadataItemRequest::assetCode)
                .toList();
        for (AssetDtos.AssetResponse scopedAsset
                : assetRepository.findAssetsInProducerScope(producer.serviceName(), producer.environment())) {
            if (!snapshotCodes.contains(scopedAsset.assetCode())
                    && scopedAsset.lifecycleStatus() != LifecycleStatus.REMOVED_BY_SNAPSHOT
                    && scopedAsset.lifecycleStatus() != LifecycleStatus.UNREGISTERED) {
                assetRepository.markRemovedBySnapshot(scopedAsset.assetId(), syncedAt);
                items.add(new MetadataDtos.MetadataSyncItemResponse(
                        scopedAsset.assetId(),
                        scopedAsset.assetCode(),
                        MetadataSyncItemStatus.REMOVED_BY_SNAPSHOT));
                removed++;
            }
        }

        return new MetadataDtos.MetadataSyncResponse(
                new MetadataDtos.MetadataSyncScope(producer.serviceName(), producer.environment()),
                created,
                updated,
                unchanged,
                removed,
                List.copyOf(items),
                syncedAt);
    }

    public MetadataDtos.MetadataListResponse listMetadata(
            String keyword,
            String domain,
            String metadataType,
            String owner,
            int page,
            int size
    ) {
        int safePage = Math.max(1, page);
        int safeSize = Math.max(1, Math.min(size, 100));
        List<MetadataDtos.MetadataSummaryResponse> filtered = assetRepository.listAssets().stream()
                .filter(asset -> matchesKeyword(asset, keyword))
                .filter(asset -> domain == null || domain.isBlank() || domain.equals(asset.domain()))
                .filter(asset -> metadataType == null || metadataType.isBlank()
                        || metadataType.equalsIgnoreCase(asset.assetType().name()))
                .filter(asset -> owner == null || owner.isBlank() || owner.equals(asset.owner()))
                .map(this::toSummary)
                .toList();
        int from = Math.min((safePage - 1) * safeSize, filtered.size());
        int to = Math.min(from + safeSize, filtered.size());
        return new MetadataDtos.MetadataListResponse(
                filtered.subList(from, to),
                safePage,
                safeSize,
                filtered.size());
    }

    public MetadataDtos.MetadataDetailResponse getMetadata(String metadataId) {
        AssetDtos.AssetResponse asset = assetRepository.findAssetById(metadataId)
                .orElseThrow(() -> new AssetNotFoundException(metadataId));
        return toDetail(new AssetDtos.AssetDetailResponse(
                asset,
                assetRepository.findFields(asset.assetId()),
                assetRepository.findActiveBinding(asset.assetId()).orElse(null)));
    }

    public MetadataDtos.MetadataMutationResponse updateMetadata(
            String metadataId,
            AssetDtos.UpdateAssetRequest request
    ) {
        AssetDtos.AssetResponse asset = assetRepository.findAssetById(metadataId)
                .orElseThrow(() -> new AssetNotFoundException(metadataId));
        AssetDtos.AssetMutationResponse response = assetService.updateRuntime(asset.assetCode(), request);
        return new MetadataDtos.MetadataMutationResponse(
                response.asset().asset().assetId(),
                response.asset().asset().assetCode(),
                "UPDATED",
                response.asset().asset().updatedAt());
    }

    public MetadataDtos.MetadataMutationResponse unregisterMetadata(
            String metadataId,
            AssetDtos.UnregisterAssetRequest request
    ) {
        AssetDtos.AssetResponse asset = assetRepository.findAssetById(metadataId)
                .orElseThrow(() -> new AssetNotFoundException(metadataId));
        AssetDtos.AssetMutationResponse response = assetService.unregisterRuntime(asset.assetCode(), request);
        return new MetadataDtos.MetadataMutationResponse(
                response.asset().asset().assetId(),
                response.asset().asset().assetCode(),
                "UNREGISTERED",
                response.asset().asset().updatedAt());
    }

    private AssetDtos.RegisterAssetRequest toRegisterRequest(MetadataDtos.MetadataItemRequest item) {
        return new AssetDtos.RegisterAssetRequest(
                item.assetCode(),
                item.assetName(),
                item.metadataType(),
                item.sourceType(),
                item.domain(),
                item.owner(),
                item.description(),
                LifecycleStatus.ACTIVE,
                item.queryable(),
                item.federatedQueryable(),
                item.schema() == null ? List.of() : item.schema().stream()
                        .map(field -> new AssetDtos.FieldRequest(
                                field.fieldName(),
                                field.fieldType(),
                                field.ordinal(),
                                field.nullable(),
                                field.partitionKey(),
                                field.primaryKey(),
                                field.eventTime(),
                                field.description(),
                                field.expression()))
                        .toList(),
                item.binding() == null ? null : new AssetDtos.PhysicalBindingRequest(
                        item.binding().sourceType(),
                        item.binding().catalog(),
                        item.binding().database(),
                        item.binding().schema(),
                        item.binding().table(),
                        item.binding().topic(),
                        item.binding().format(),
                        item.binding().locationUri(),
                        item.binding().connectionRef(),
                        item.binding().queryAdapter(),
                        item.binding().properties()));
    }

    private MetadataDtos.MetadataSummaryResponse toSummary(AssetDtos.AssetResponse asset) {
        return new MetadataDtos.MetadataSummaryResponse(
                asset.assetId(),
                asset.assetCode(),
                asset.assetName(),
                asset.assetType(),
                asset.engine(),
                asset.domain(),
                asset.owner(),
                asset.queryable());
    }

    private MetadataDtos.MetadataDetailResponse toDetail(AssetDtos.AssetDetailResponse detail) {
        AssetDtos.AssetResponse asset = detail.asset();
        return new MetadataDtos.MetadataDetailResponse(
                asset.assetId(),
                asset.assetCode(),
                asset.assetName(),
                asset.assetType(),
                asset.engine(),
                asset.domain(),
                asset.owner(),
                asset.description(),
                asset.queryable(),
                asset.federatedQueryable(),
                detail.fields().stream()
                        .map(field -> new MetadataDtos.MetadataFieldResponse(
                                field.fieldName(),
                                field.fieldType(),
                                field.ordinalPosition(),
                                field.nullable(),
                                field.partitionKey(),
                                field.primaryKey(),
                                field.eventTime(),
                                field.description(),
                                field.expression()))
                        .toList(),
                toBinding(detail.binding()),
                asset.createdAt(),
                asset.updatedAt());
    }

    private MetadataDtos.MetadataBindingResponse toBinding(AssetDtos.PhysicalBindingResponse binding) {
        if (binding == null) {
            return null;
        }
        String qualifiedName = binding.topicName() != null
                ? binding.topicName()
                : String.join(".",
                        List.of(binding.catalogName(), binding.databaseName(), binding.tableName()).stream()
                                .filter(value -> value != null && !value.isBlank())
                                .toList());
        return new MetadataDtos.MetadataBindingResponse(
                binding.engine(),
                binding.catalogName(),
                binding.databaseName(),
                binding.schemaName(),
                binding.tableName(),
                binding.topicName(),
                qualifiedName,
                binding.format(),
                binding.locationUri(),
                binding.connectionRef(),
                binding.queryAdapter(),
                binding.properties());
    }

    private boolean matchesKeyword(AssetDtos.AssetResponse asset, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }
        String lower = keyword.toLowerCase(Locale.ROOT);
        return contains(asset.assetCode(), lower)
                || contains(asset.assetName(), lower)
                || contains(asset.description(), lower);
    }

    private boolean contains(String value, String lowerKeyword) {
        return value != null && value.toLowerCase(Locale.ROOT).contains(lowerKeyword);
    }

    private String declarationHash(MetadataDtos.MetadataItemRequest item) {
        try {
            String json = objectMapper.writeValueAsString(item);
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(json.getBytes(StandardCharsets.UTF_8));
            return "sha256:" + HexFormat.of().formatHex(digest);
        } catch (Exception ex) {
            throw new MetadataDataAccessException("Failed to calculate metadata declaration hash", ex);
        }
    }
}
```

- [ ] **Step 5: Implement metadata controller**

Create `MetadataController.java`:

```java
package io.datagov.server.metadata;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.MetadataDtos;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/rest/oss/inner/modelengineservice/v1")
public class MetadataController {
    private final MetadataService metadataService;

    public MetadataController(MetadataService metadataService) {
        this.metadataService = metadataService;
    }

    @PostMapping("/metadata/register")
    public MetadataDtos.MetadataSyncResponse registerSnapshot(
            @Valid @RequestBody MetadataDtos.MetadataSnapshotRegisterRequest request
    ) {
        return metadataService.registerSnapshot(request);
    }

    @GetMapping("/metadata")
    public MetadataDtos.MetadataListResponse listMetadata(
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "domain", required = false) String domain,
            @RequestParam(name = "metadataType", required = false) String metadataType,
            @RequestParam(name = "owner", required = false) String owner,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "size", defaultValue = "20") int size
    ) {
        return metadataService.listMetadata(keyword, domain, metadataType, owner, page, size);
    }

    @GetMapping("/metadata/{metadataId}")
    public MetadataDtos.MetadataDetailResponse getMetadata(@PathVariable("metadataId") String metadataId) {
        return metadataService.getMetadata(metadataId);
    }

    @PatchMapping("/metadata/{metadataId}")
    public MetadataDtos.MetadataMutationResponse updateMetadata(
            @PathVariable("metadataId") String metadataId,
            @Valid @RequestBody AssetDtos.UpdateAssetRequest request
    ) {
        return metadataService.updateMetadata(metadataId, request);
    }

    @DeleteMapping("/metadata/{metadataId}")
    public MetadataDtos.MetadataMutationResponse unregisterMetadata(
            @PathVariable("metadataId") String metadataId,
            @Valid @RequestBody AssetDtos.UnregisterAssetRequest request
    ) {
        return metadataService.unregisterMetadata(metadataId, request);
    }
}
```

- [ ] **Step 6: Run formal metadata API tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=MetadataControllerTest test
```

Expected: `BUILD SUCCESS`.

## Task 4: SDK Startup Metadata Snapshot Registration

**Files:**

- Modify: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DataGovClient.java`
- Modify: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DefaultDataGovClient.java`
- Modify: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovProperties.java`
- Modify: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovStartupRegistrar.java`
- Create: `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/DefaultDataGovClientMetadataTest.java`
- Modify: `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/spring/DataGovAutoConfigurationTest.java`

- [ ] **Step 1: Add failing SDK client test**

Create `DefaultDataGovClientMetadataTest.java`:

```java
package io.datagov.sdk;

import io.datagov.common.dto.MetadataDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.MetadataProducerType;
import io.datagov.common.enums.MetadataSyncItemStatus;
import io.datagov.common.enums.MetadataSyncMode;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class DefaultDataGovClientMetadataTest {
    @Test
    void registerMetadataSnapshotUsesFormalMetadataPath() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://data-gov");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        DefaultDataGovClient client = new DefaultDataGovClient(builder.build());

        server.expect(once(), requestTo("http://data-gov/rest/oss/inner/modelengineservice/v1/metadata/register"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withSuccess("""
                        {
                          "syncScope": {"serviceName": "rno-profile-service", "environment": "prod"},
                          "createdCount": 1,
                          "updatedCount": 0,
                          "unchangedCount": 0,
                          "removedBySnapshotCount": 0,
                          "items": [
                            {"metadataId": "asset_1", "assetCode": "ads_cell_profile", "status": "CREATED"}
                          ],
                          "syncedAt": "2026-06-13T00:00:00Z"
                        }
                        """, org.springframework.http.MediaType.APPLICATION_JSON));

        MetadataDtos.MetadataSyncResponse response = client.registerMetadataSnapshot(
                new MetadataDtos.MetadataSnapshotRegisterRequest(
                        new MetadataDtos.ProducerRequest(
                                "rno-profile-service",
                                MetadataProducerType.MICROSERVICE,
                                "network-team",
                                "prod",
                                "pod-1"),
                        MetadataSyncMode.FULL,
                        List.of(new MetadataDtos.MetadataItemRequest(
                                "ads_cell_profile",
                                "ADS Cell Profile",
                                AssetType.TABLE,
                                AssetEngine.STARROCKS,
                                "wireless",
                                "network-team",
                                null,
                                true,
                                true,
                                List.of(),
                                null,
                                null))));

        assertThat(response.createdCount()).isEqualTo(1);
        assertThat(response.items().get(0).status()).isEqualTo(MetadataSyncItemStatus.CREATED);
        assertThat(response.syncedAt()).isEqualTo(Instant.parse("2026-06-13T00:00:00Z"));
        server.verify();
    }
}
```

- [ ] **Step 2: Add client method**

Modify `DataGovClient.java`:

```java
MetadataDtos.MetadataSyncResponse registerMetadataSnapshot(
        MetadataDtos.MetadataSnapshotRegisterRequest request);
```

Add import:

```java
import io.datagov.common.dto.MetadataDtos;
```

Modify `DefaultDataGovClient.java`:

```java
@Override
public MetadataDtos.MetadataSyncResponse registerMetadataSnapshot(
        MetadataDtos.MetadataSnapshotRegisterRequest request) {
    try {
        return restClient.post()
                .uri("/rest/oss/inner/modelengineservice/v1/metadata/register")
                .body(request)
                .retrieve()
                .body(MetadataDtos.MetadataSyncResponse.class);
    } catch (RuntimeException exception) {
        throw new DataGovClientException("Failed to register metadata snapshot", exception);
    }
}
```

- [ ] **Step 3: Add SDK metadata properties**

Modify `DataGovProperties.java`:

```java
private List<Metadata> metadata = List.of();

public List<Metadata> metadata() {
    return metadata;
}

public List<Metadata> getMetadata() {
    return metadata;
}

public void setMetadata(List<Metadata> metadata) {
    this.metadata = metadata == null ? List.of() : metadata;
}

public static class Metadata {
    private String assetCode;
    private String assetName;
    private io.datagov.common.enums.AssetType metadataType;
    private io.datagov.common.enums.AssetEngine sourceType;
    private String domain;
    private String owner;
    private String description;
    private boolean queryable = true;
    private boolean federatedQueryable = true;
    private List<Field> schema = List.of();
    private Binding binding;

    public String assetCode() { return assetCode; }
    public String getAssetCode() { return assetCode; }
    public void setAssetCode(String assetCode) { this.assetCode = assetCode; }
    public String assetName() { return assetName; }
    public String getAssetName() { return assetName; }
    public void setAssetName(String assetName) { this.assetName = assetName; }
    public io.datagov.common.enums.AssetType metadataType() { return metadataType; }
    public io.datagov.common.enums.AssetType getMetadataType() { return metadataType; }
    public void setMetadataType(io.datagov.common.enums.AssetType metadataType) { this.metadataType = metadataType; }
    public io.datagov.common.enums.AssetEngine sourceType() { return sourceType; }
    public io.datagov.common.enums.AssetEngine getSourceType() { return sourceType; }
    public void setSourceType(io.datagov.common.enums.AssetEngine sourceType) { this.sourceType = sourceType; }
    public String domain() { return domain; }
    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public String owner() { return owner; }
    public String getOwner() { return owner; }
    public void setOwner(String owner) { this.owner = owner; }
    public String description() { return description; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public boolean queryable() { return queryable; }
    public boolean isQueryable() { return queryable; }
    public void setQueryable(boolean queryable) { this.queryable = queryable; }
    public boolean federatedQueryable() { return federatedQueryable; }
    public boolean isFederatedQueryable() { return federatedQueryable; }
    public void setFederatedQueryable(boolean federatedQueryable) { this.federatedQueryable = federatedQueryable; }
    public List<Field> schema() { return schema; }
    public List<Field> getSchema() { return schema; }
    public void setSchema(List<Field> schema) { this.schema = schema == null ? List.of() : schema; }
    public Binding binding() { return binding; }
    public Binding getBinding() { return binding; }
    public void setBinding(Binding binding) { this.binding = binding; }
}

public static class Field {
    private String fieldName;
    private String fieldType;
    private Integer ordinal;
    private Boolean nullable;
    private Boolean partitionKey;
    private Boolean primaryKey;
    private Boolean eventTime;
    private String description;
    private String expression;

    public String fieldName() { return fieldName; }
    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public String fieldType() { return fieldType; }
    public String getFieldType() { return fieldType; }
    public void setFieldType(String fieldType) { this.fieldType = fieldType; }
    public Integer ordinal() { return ordinal; }
    public Integer getOrdinal() { return ordinal; }
    public void setOrdinal(Integer ordinal) { this.ordinal = ordinal; }
    public Boolean nullable() { return nullable; }
    public Boolean getNullable() { return nullable; }
    public void setNullable(Boolean nullable) { this.nullable = nullable; }
    public Boolean partitionKey() { return partitionKey; }
    public Boolean getPartitionKey() { return partitionKey; }
    public void setPartitionKey(Boolean partitionKey) { this.partitionKey = partitionKey; }
    public Boolean primaryKey() { return primaryKey; }
    public Boolean getPrimaryKey() { return primaryKey; }
    public void setPrimaryKey(Boolean primaryKey) { this.primaryKey = primaryKey; }
    public Boolean eventTime() { return eventTime; }
    public Boolean getEventTime() { return eventTime; }
    public void setEventTime(Boolean eventTime) { this.eventTime = eventTime; }
    public String description() { return description; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String expression() { return expression; }
    public String getExpression() { return expression; }
    public void setExpression(String expression) { this.expression = expression; }
}

public static class Binding {
    private io.datagov.common.enums.AssetEngine sourceType;
    private String catalog;
    private String database;
    private String schema;
    private String table;
    private String topic;
    private String format;
    private String locationUri;
    private String connectionRef;
    private String queryAdapter;
    private java.util.Map<String, Object> properties = java.util.Map.of();

    public io.datagov.common.enums.AssetEngine sourceType() { return sourceType; }
    public io.datagov.common.enums.AssetEngine getSourceType() { return sourceType; }
    public void setSourceType(io.datagov.common.enums.AssetEngine sourceType) { this.sourceType = sourceType; }
    public String catalog() { return catalog; }
    public String getCatalog() { return catalog; }
    public void setCatalog(String catalog) { this.catalog = catalog; }
    public String database() { return database; }
    public String getDatabase() { return database; }
    public void setDatabase(String database) { this.database = database; }
    public String schema() { return schema; }
    public String getSchema() { return schema; }
    public void setSchema(String schema) { this.schema = schema; }
    public String table() { return table; }
    public String getTable() { return table; }
    public void setTable(String table) { this.table = table; }
    public String topic() { return topic; }
    public String getTopic() { return topic; }
    public void setTopic(String topic) { this.topic = topic; }
    public String format() { return format; }
    public String getFormat() { return format; }
    public void setFormat(String format) { this.format = format; }
    public String locationUri() { return locationUri; }
    public String getLocationUri() { return locationUri; }
    public void setLocationUri(String locationUri) { this.locationUri = locationUri; }
    public String connectionRef() { return connectionRef; }
    public String getConnectionRef() { return connectionRef; }
    public void setConnectionRef(String connectionRef) { this.connectionRef = connectionRef; }
    public String queryAdapter() { return queryAdapter; }
    public String getQueryAdapter() { return queryAdapter; }
    public void setQueryAdapter(String queryAdapter) { this.queryAdapter = queryAdapter; }
    public java.util.Map<String, Object> properties() { return properties; }
    public java.util.Map<String, Object> getProperties() { return properties; }
    public void setProperties(java.util.Map<String, Object> properties) {
        this.properties = properties == null ? java.util.Map.of() : properties;
    }
}
```

- [ ] **Step 4: Update startup registrar request assembly**

Modify `DataGovStartupRegistrar.onApplicationEvent` so metadata and subscriptions can run independently:

```java
@Override
public void onApplicationEvent(ApplicationReadyEvent event) {
    try {
        if (!properties.metadata().isEmpty()) {
            dataGovClient.registerMetadataSnapshot(toMetadataRequest());
        }
        if (!properties.subscriptions().isEmpty()) {
            dataGovClient.registerSubscriptions(toRequest());
        }
    } catch (RuntimeException exception) {
        if (properties.failFast()) {
            throw exception;
        }
    }
}
```

Add `toMetadataRequest()` and mapping helpers:

```java
MetadataDtos.MetadataSnapshotRegisterRequest toMetadataRequest() {
    MetadataDtos.ProducerRequest producer = new MetadataDtos.ProducerRequest(
            properties.consumer().name(),
            MetadataProducerType.MICROSERVICE,
            properties.consumer().owner(),
            properties.consumer().environment(),
            properties.consumer().instanceId());
    return new MetadataDtos.MetadataSnapshotRegisterRequest(
            producer,
            MetadataSyncMode.FULL,
            properties.metadata().stream().map(this::toMetadataItem).toList());
}

private MetadataDtos.MetadataItemRequest toMetadataItem(DataGovProperties.Metadata metadata) {
    return new MetadataDtos.MetadataItemRequest(
            metadata.assetCode(),
            metadata.assetName(),
            metadata.metadataType(),
            metadata.sourceType(),
            metadata.domain(),
            metadata.owner(),
            metadata.description(),
            metadata.queryable(),
            metadata.federatedQueryable(),
            metadata.schema().stream().map(this::toMetadataField).toList(),
            metadata.binding() == null ? null : toMetadataBinding(metadata.binding()),
            null);
}
```

- [ ] **Step 5: Extend autoconfiguration test**

Modify `DataGovAutoConfigurationTest.createsClientWhenEnabled` by adding property values:

```java
"data-gov.metadata[0].asset-code=ads_cell_profile",
"data-gov.metadata[0].asset-name=ADS Cell Profile",
"data-gov.metadata[0].metadata-type=TABLE",
"data-gov.metadata[0].source-type=STARROCKS",
"data-gov.metadata[0].domain=wireless",
"data-gov.metadata[0].owner=network-team",
"data-gov.metadata[0].schema[0].field-name=cell_id",
"data-gov.metadata[0].schema[0].field-type=varchar",
"data-gov.metadata[0].binding.source-type=STARROCKS",
"data-gov.metadata[0].binding.catalog=default_catalog",
"data-gov.metadata[0].binding.database=ads",
"data-gov.metadata[0].binding.table=ads_cell_profile"
```

Add assertion:

```java
assertThat(properties.metadata()).hasSize(1);
assertThat(properties.metadata().get(0).assetCode()).isEqualTo("ads_cell_profile");
```

- [ ] **Step 6: Run SDK tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-sdk -am test
```

Expected: `BUILD SUCCESS`.

## Task 5: Full Verification

**Files:**

- Verify all files touched by Tasks 1-4.

- [ ] **Step 1: Run full Maven tests**

Run:

```powershell
cd data-gov-platform
mvn test
```

Expected: `BUILD SUCCESS`.

- [ ] **Step 2: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no output.

- [ ] **Step 3: Confirm no infrastructure files changed**

Run:

```powershell
git status --short -- app-compose.yml docker-compose.yml compose.yaml data-gov-platform\app-compose.yml
```

Expected: no output.

- [ ] **Step 4: Inspect changed files**

Run:

```powershell
git status --short
```

Expected changed files are limited to metadata DTOs/enums, lifecycle enum, V7 migration, metadata server package, asset repository support, SDK metadata snapshot client/properties/registrar, metadata tests, SDK tests, and this plan document.

## Review Checklist

Before merge:

- Formal `POST /rest/oss/inner/modelengineservice/v1/metadata/register` creates metadata from a full snapshot.
- Repeating the same snapshot returns `UNCHANGED` and does not increment `schemaVersion`.
- Changing one metadata declaration returns `UPDATED`.
- Missing scoped metadata is soft-marked `REMOVED_BY_SNAPSHOT` and made non-queryable.
- Formal metadata list and detail APIs use `metadataId = assetId`.
- Formal runtime `PATCH` and `DELETE` resolve by `metadataId` and reuse existing runtime event behavior.
- SDK startup can register metadata snapshots without requiring subscription declarations.
- Existing `/api/...` routes still pass their tests.
- No Docker Compose files are changed.

## Plan Self-Review

Spec coverage:

- Formal metadata register path: Task 3.
- Startup full snapshot semantics: Task 3 and Task 4.
- Metadata list/detail discovery: Task 3.
- Runtime modify/unregister by metadata ID: Task 3.
- SDK formal metadata register call: Task 4.
- No infrastructure change: Task 5.

Placeholder scan:

- Clean. The plan does not contain placeholder markers, open-ended test instructions, or deferred code blocks inside the scoped implementation.

Type consistency:

- `metadataId` maps to existing `assetId`.
- `metadataType` maps to existing `AssetType`.
- `sourceType` maps to existing `AssetEngine`.
- Formal metadata mutation reuses existing `AssetDtos.UpdateAssetRequest` and `AssetDtos.UnregisterAssetRequest` in this slice.
- `LifecycleStatus.REMOVED_BY_SNAPSHOT` and `LifecycleStatus.UNREGISTERED` are added before any code references them.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-13-formal-metadata-snapshot-api.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.
