# Lineage And Impact Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GaussDB-backed asset lineage and first-phase impact analysis APIs to the Java data governance platform.

**Architecture:** Extend the current Spring Boot JDBC style. `data-gov-common` owns DTOs/enums, `data-gov-server` owns Flyway migrations, repositories, services, controllers, and MockMvc integration tests. The first slice supports asset-level lineage reads/writes and keeps field-level lineage tables for later expansion.

**Tech Stack:** Java 17, Spring Boot 3.3, JDBC/JdbcTemplate, Flyway, H2 tests, GaussDB/PostgreSQL-compatible SQL.

---

## Scope

Build this phase:

- Asset-level lineage table and API.
- Field-level lineage table for future use, without public field-lineage API in this phase.
- Upstream/downstream lineage graph query by `assetCode`.
- Impact analysis by `assetCode`, combining downstream lineage, active subscriptions, and recent query records.
- Tests proving traversal depth, cycle handling, subscription aggregation, and query-record aggregation.

Do not build this phase:

- Automatic lineage generation from Flink/Spark job completion.
- Runtime job lifecycle records.
- Kafka event notifications.
- Governance drift checks.
- Frontend UI.
- Docker Compose or shared infrastructure changes.

## Existing Context

Current modules:

- `data-gov-platform/data-gov-common`: DTOs and enums.
- `data-gov-platform/data-gov-server`: Spring Boot server, Flyway migrations, JDBC repositories.
- `data-gov-platform/data-gov-sdk`: Java SDK.

Existing relevant tables:

- `data_asset`
- `asset_field`
- `consumer`
- `subscription`
- `query_record`

Existing relevant patterns:

- `AssetRepository` resolves assets and fields through `JdbcTemplate`.
- Controllers use `/api/assets/{assetCode}/...`.
- Tests use `@SpringBootTest`, `@AutoConfigureMockMvc`, `@ActiveProfiles("test")`, and H2 Flyway migrations.
- Error responses use `ApiExceptionHandler` and a JSON body with `error` plus `message` or `detail`.

## API Contract

Add endpoints:

```http
POST /api/lineage/edges
GET  /api/assets/{assetCode}/lineage?direction=up|down&depth=5
GET  /api/assets/{assetCode}/impact?depth=5&recentDays=30
```

Use `assetCode` in URLs to stay consistent with current implemented APIs.

## Data Model

Add Flyway migration:

- `data-gov-platform/data-gov-server/src/main/resources/db/migration/V4__lineage_edges.sql`

Create asset-level lineage:

```sql
create table lineage_edge (
    edge_id varchar(64) primary key,
    source_asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    target_asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    relation_type varchar(32) not null,
    producer varchar(128),
    process_name varchar(256),
    job_name varchar(256),
    description text,
    properties text,
    active boolean not null default true,
    created_at timestamp not null,
    updated_at timestamp not null
);

create index idx_lineage_edge_source on lineage_edge(source_asset_id);
create index idx_lineage_edge_target on lineage_edge(target_asset_id);
create index idx_lineage_edge_active on lineage_edge(active);
create index idx_lineage_edge_relation_type on lineage_edge(relation_type);
```

Create field-level lineage storage:

```sql
create table lineage_field_edge (
    field_edge_id varchar(64) primary key,
    lineage_edge_id varchar(64) not null references lineage_edge(edge_id) on delete cascade,
    source_field_id varchar(64) references asset_field(field_id) on delete set null,
    target_field_id varchar(64) references asset_field(field_id) on delete set null,
    transform_expression text,
    description text,
    properties text,
    active boolean not null default true,
    created_at timestamp not null,
    updated_at timestamp not null
);

create index idx_lineage_field_edge_lineage on lineage_field_edge(lineage_edge_id);
create index idx_lineage_field_edge_source_field on lineage_field_edge(source_field_id);
create index idx_lineage_field_edge_target_field on lineage_field_edge(target_field_id);
```

## DTOs And Enums

Add enums:

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageDirection.java`
- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageRelationType.java`

Enum values:

```java
public enum LineageDirection {
    UP,
    DOWN
}
```

```java
public enum LineageRelationType {
    PRODUCES,
    DERIVES,
    READS,
    WRITES,
    DEPENDS_ON
}
```

Add DTO file:

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/LineageDtos.java`

Use this structure:

```java
package io.datagov.common.dto;

import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LineageDirection;
import io.datagov.common.enums.LineageRelationType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class LineageDtos {
    private LineageDtos() {
    }

    public record CreateLineageEdgeRequest(
            @NotBlank String sourceAssetCode,
            @NotBlank String targetAssetCode,
            @NotNull LineageRelationType relationType,
            String producer,
            String processName,
            String jobName,
            String description,
            Map<String, Object> properties
    ) {
    }

    public record LineageAssetNode(
            String assetId,
            String assetCode,
            String assetName,
            AssetType assetType,
            AssetEngine engine
    ) {
    }

    public record LineageEdgeResponse(
            String edgeId,
            LineageAssetNode source,
            LineageAssetNode target,
            LineageRelationType relationType,
            String producer,
            String processName,
            String jobName,
            String description,
            Map<String, Object> properties,
            boolean active,
            Instant createdAt,
            Instant updatedAt
    ) {
    }

    public record LineageGraphResponse(
            LineageAssetNode root,
            LineageDirection direction,
            int depth,
            List<LineageAssetNode> nodes,
            List<LineageEdgeResponse> edges
    ) {
    }

    public record ImpactSubscription(
            String subscriptionId,
            String assetCode,
            String consumerId,
            String consumerName,
            String usageMode,
            List<String> declaredFields,
            Instant lastRuntimeSeenAt
    ) {
    }

    public record ImpactQueryUsage(
            String queryId,
            String requestType,
            String status,
            List<String> referencedAssetCodes,
            Instant createdAt
    ) {
    }

    public record ImpactResponse(
            LineageAssetNode root,
            int depth,
            LineageGraphResponse downstreamLineage,
            List<ImpactSubscription> subscriptions,
            List<ImpactQueryUsage> recentQueries
    ) {
    }
}
```

## Server Package Layout

Create package:

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage`

Classes:

- `LineageController`
- `LineageService`
- `LineageRepository`
- `LineageDataAccessException`
- `LineageValidationException`

Modify:

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`

Tests:

- `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/lineage/LineageControllerTest.java`

## Behavior

### Create Edge

`POST /api/lineage/edges` behavior:

1. Validate request body.
2. Resolve `sourceAssetCode` and `targetAssetCode`.
3. Reject self-edge where source asset equals target asset with error `INVALID_LINEAGE_EDGE`.
4. Insert active lineage edge.
5. Return `LineageEdgeResponse`.

Do not upsert in this phase. Multiple edges with different `relationType`, `processName`, or `jobName` can represent separate business relationships.

### Query Lineage

`GET /api/assets/{assetCode}/lineage?direction=up|down&depth=5` behavior:

1. Resolve root asset.
2. Default `direction` to `DOWN`.
3. Default `depth` to `5`.
4. Clamp `depth` to `1..10`.
5. Traverse active lineage edges in Java using repository neighbor queries.
6. Stop traversal when depth reaches the clamp value.
7. Keep a visited edge set to avoid duplicate edges.
8. Keep a visited `(assetId, level)` or shortest-depth map to avoid infinite cycles.
9. Return unique nodes and edges.

Use Java traversal instead of database recursive CTE in this phase because it is easier to keep compatible across H2 and GaussDB tests. Depth is capped at 10, so repeated neighbor queries are acceptable.

### Impact Analysis

`GET /api/assets/{assetCode}/impact?depth=5&recentDays=30` behavior:

1. Resolve root asset.
2. Build downstream lineage graph with the same depth clamp.
3. Collect impacted asset codes from the downstream graph, including the root.
4. List active subscriptions for impacted assets.
5. List recent query records where:
   - `asset_id` is one of the impacted assets, or
   - `referenced_asset_codes` text contains one of the impacted asset codes.
6. Default `recentDays` to `30`.
7. Clamp `recentDays` to `1..365`.
8. Limit recent query records to 100 rows ordered by newest first.

This is a first-phase impact report. It is intentionally not a full graph centrality or blast-radius scoring engine.

## Error Handling

Add handlers:

- `LineageValidationException` -> HTTP 400
- `LineageDataAccessException` -> HTTP 500

Error codes:

- `INVALID_LINEAGE_EDGE`
- `LINEAGE_DATA_ACCESS_ERROR`

Missing assets continue to use existing `AssetNotFoundException` -> HTTP 404.

## Task 1: DTOs, Enums, And Migration

**Files:**

- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageDirection.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageRelationType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/LineageDtos.java`
- Create: `data-gov-platform/data-gov-server/src/main/resources/db/migration/V4__lineage_edges.sql`

- [ ] **Step 1: Write DTOs and enums**

Create the exact DTO and enum structures from the "DTOs And Enums" section.

- [ ] **Step 2: Write migration**

Create `V4__lineage_edges.sql` using the exact SQL from the "Data Model" section.

- [ ] **Step 3: Run module tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-common,data-gov-server -am test
```

Expected:

```text
BUILD SUCCESS
```

- [ ] **Step 4: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

## Task 2: Lineage Edge API And Graph Traversal

**Files:**

- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageController.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageService.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageRepository.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageDataAccessException.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageValidationException.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/lineage/LineageControllerTest.java`

- [ ] **Step 1: Write failing API tests**

Create `LineageControllerTest` with these tests:

```java
@Test
void createsLineageEdgeAndQueriesDownstreamGraph() throws Exception {
    registerTableAsset("ods_ue_signal", "KAFKA");
    registerTableAsset("dwd_session_qos", "HIVE");
    registerTableAsset("ads_cell_profile", "STARROCKS");

    mockMvc.perform(post("/api/lineage/edges")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                            {
                              "sourceAssetCode": "ods_ue_signal",
                              "targetAssetCode": "dwd_session_qos",
                              "relationType": "PRODUCES",
                              "producer": "flink",
                              "processName": "ue-signal-clean",
                              "jobName": "ue-signal-clean-job",
                              "description": "ODS stream produces DWD session QoS"
                            }
                            """))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.source.assetCode").value("ods_ue_signal"))
            .andExpect(jsonPath("$.target.assetCode").value("dwd_session_qos"))
            .andExpect(jsonPath("$.relationType").value("PRODUCES"));

    mockMvc.perform(post("/api/lineage/edges")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                            {
                              "sourceAssetCode": "dwd_session_qos",
                              "targetAssetCode": "ads_cell_profile",
                              "relationType": "DERIVES"
                            }
                            """))
            .andExpect(status().isOk());

    mockMvc.perform(get("/api/assets/ods_ue_signal/lineage")
                    .param("direction", "down")
                    .param("depth", "2"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.root.assetCode").value("ods_ue_signal"))
            .andExpect(jsonPath("$.direction").value("DOWN"))
            .andExpect(jsonPath("$.nodes", hasSize(3)))
            .andExpect(jsonPath("$.edges", hasSize(2)));
}
```

```java
@Test
void upstreamLineageHonorsDepthLimit() throws Exception {
    registerTableAsset("ods_ue_signal", "KAFKA");
    registerTableAsset("dwd_session_qos", "HIVE");
    registerTableAsset("ads_cell_profile", "STARROCKS");
    createEdge("ods_ue_signal", "dwd_session_qos", "PRODUCES");
    createEdge("dwd_session_qos", "ads_cell_profile", "DERIVES");

    mockMvc.perform(get("/api/assets/ads_cell_profile/lineage")
                    .param("direction", "up")
                    .param("depth", "1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.nodes", hasSize(2)))
            .andExpect(jsonPath("$.edges", hasSize(1)))
            .andExpect(jsonPath("$.edges[0].source.assetCode").value("dwd_session_qos"));
}
```

```java
@Test
void lineageTraversalDoesNotLoopOnCycles() throws Exception {
    registerTableAsset("asset_a", "STARROCKS");
    registerTableAsset("asset_b", "STARROCKS");
    createEdge("asset_a", "asset_b", "DEPENDS_ON");
    createEdge("asset_b", "asset_a", "DEPENDS_ON");

    mockMvc.perform(get("/api/assets/asset_a/lineage")
                    .param("direction", "down")
                    .param("depth", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.nodes", hasSize(2)))
            .andExpect(jsonPath("$.edges", hasSize(2)));
}
```

```java
@Test
void selfLineageEdgeReturnsBadRequest() throws Exception {
    registerTableAsset("ads_cell_profile", "STARROCKS");

    mockMvc.perform(post("/api/lineage/edges")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                            {
                              "sourceAssetCode": "ads_cell_profile",
                              "targetAssetCode": "ads_cell_profile",
                              "relationType": "DERIVES"
                            }
                            """))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error").value("INVALID_LINEAGE_EDGE"));
}
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=LineageControllerTest test
```

Expected: fails because lineage controller/package does not exist yet.

- [ ] **Step 3: Implement repository and service**

Implement:

- `LineageRepository.insertEdge(...)`
- `LineageRepository.findActiveOutgoing(assetId)`
- `LineageRepository.findActiveIncoming(assetId)`
- `LineageService.createEdge(...)`
- `LineageService.getLineage(assetCode, direction, depth)`

Use IDs like:

```java
"lin_" + UUID.randomUUID().toString().replace("-", "")
```

Use traversal data structures:

```java
Map<String, LineageAssetNode> nodesById = new LinkedHashMap<>();
Map<String, LineageEdgeResponse> edgesById = new LinkedHashMap<>();
Map<String, Integer> shortestDepthByAssetId = new HashMap<>();
ArrayDeque<TraversalItem> queue = new ArrayDeque<>();
```

Only enqueue a neighbor when the next depth is lower than any previously recorded depth for that asset.

- [ ] **Step 4: Implement controller and exception handling**

Routes:

```java
@PostMapping("/lineage/edges")
public LineageDtos.LineageEdgeResponse createEdge(@Valid @RequestBody LineageDtos.CreateLineageEdgeRequest request)
```

```java
@GetMapping("/assets/{assetCode}/lineage")
public LineageDtos.LineageGraphResponse getLineage(
        @PathVariable String assetCode,
        @RequestParam(defaultValue = "DOWN") LineageDirection direction,
        @RequestParam(defaultValue = "5") int depth)
```

Add `ApiExceptionHandler` methods for `LineageValidationException` and `LineageDataAccessException`.

- [ ] **Step 5: Run tests and verify green**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=LineageControllerTest test
```

Expected:

```text
BUILD SUCCESS
```

## Task 3: Impact Analysis API

**Files:**

- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageService.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageRepository.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageController.java`
- Modify: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/lineage/LineageControllerTest.java`

- [ ] **Step 1: Add failing impact tests**

Append these tests to `LineageControllerTest`:

```java
@Test
void impactIncludesDownstreamSubscriptionsAndRecentQueries() throws Exception {
    registerTableAsset("dwd_session_qos", "HIVE");
    registerTableAsset("ads_cell_profile", "STARROCKS");
    createEdge("dwd_session_qos", "ads_cell_profile", "DERIVES");
    createSubscription("ads_cell_profile", "rno-dashboard");
    insertQueryRecordReferencing("ads_cell_profile");

    mockMvc.perform(get("/api/assets/dwd_session_qos/impact")
                    .param("depth", "3")
                    .param("recentDays", "30"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.root.assetCode").value("dwd_session_qos"))
            .andExpect(jsonPath("$.downstreamLineage.edges", hasSize(1)))
            .andExpect(jsonPath("$.subscriptions[0].consumerName").value("rno-dashboard"))
            .andExpect(jsonPath("$.recentQueries[0].referencedAssetCodes[0]").value("ads_cell_profile"));
}
```

```java
@Test
void impactRecentDaysFiltersOldQueries() throws Exception {
    registerTableAsset("dwd_session_qos", "HIVE");
    insertOldQueryRecordReferencing("dwd_session_qos", 60);

    mockMvc.perform(get("/api/assets/dwd_session_qos/impact")
                    .param("recentDays", "30"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.recentQueries", hasSize(0)));
}
```

Test helper SQL can insert directly into `query_record` using `JdbcTemplate`.

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=LineageControllerTest test
```

Expected: fails because `/impact` endpoint is not implemented.

- [ ] **Step 3: Implement repository aggregation queries**

Add:

```java
List<LineageDtos.ImpactSubscription> findActiveSubscriptionsForAssetIds(List<String> assetIds)
```

SQL:

```sql
select s.subscription_id, a.asset_code, s.consumer_id, c.consumer_name, s.usage_mode,
       s.declared_fields, s.last_runtime_seen_at
from subscription s
join data_asset a on a.asset_id = s.asset_id
join consumer c on c.consumer_id = s.consumer_id
where s.status = 'ACTIVE'
  and s.asset_id in (...)
order by a.asset_code, c.consumer_name
```

Add:

```java
List<LineageDtos.ImpactQueryUsage> findRecentQueriesForAssetCodes(
        List<String> assetIds,
        List<String> assetCodes,
        Instant since,
        int limit)
```

Use a dynamic `where` clause with `asset_id in (...)` and `lower(referenced_asset_codes) like ?` for each asset code. This is intentionally lightweight because `referenced_asset_codes` is stored as JSON text in the first phase.

- [ ] **Step 4: Implement service and controller**

Add service method:

```java
public LineageDtos.ImpactResponse getImpact(String assetCode, int depth, int recentDays)
```

Add controller method:

```java
@GetMapping("/assets/{assetCode}/impact")
public LineageDtos.ImpactResponse getImpact(
        @PathVariable String assetCode,
        @RequestParam(defaultValue = "5") int depth,
        @RequestParam(defaultValue = "30") int recentDays)
```

Clamp `recentDays`:

```java
int days = Math.max(1, Math.min(recentDays, 365));
```

- [ ] **Step 5: Run tests and verify green**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=LineageControllerTest test
```

Expected:

```text
BUILD SUCCESS
```

## Task 4: Full Verification

**Files:**

- No new production files.
- Verify all files touched by Tasks 1-3.

- [ ] **Step 1: Run full Maven tests**

Run:

```powershell
cd data-gov-platform
mvn test
```

Expected:

```text
BUILD SUCCESS
```

- [ ] **Step 2: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 3: Confirm no infrastructure files changed**

Run:

```powershell
git status --short -- app-compose.yml docker-compose.yml compose.yaml data-gov-platform\app-compose.yml
```

Expected: no output.

If infrastructure files are changed, revert only those changes if they were created by this lineage-impact phase. Do not revert unrelated user changes.

## Review Checklist

Before merge:

- `lineage_edge` and `lineage_field_edge` exist in V4 migration.
- `POST /api/lineage/edges` creates asset-level active edges.
- `GET /api/assets/{assetCode}/lineage` supports `UP`, `DOWN`, depth limit, and cycles.
- `GET /api/assets/{assetCode}/impact` combines downstream lineage, active subscriptions, and recent query records.
- Kafka assets can participate in lineage as assets, but query behavior remains unchanged.
- No Flink/Spark automatic lineage generation was added.
- No Docker Compose files were changed.

