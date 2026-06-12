# Drift Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first governance drift analyzer that records declared-unused, undeclared-usage, and stale-declaration findings from existing subscription and query audit data.

**Architecture:** Extend the current Spring Boot JDBC style. `data-gov-common` owns drift enums and DTOs, `data-gov-server` owns the Flyway table, repository, service, and `/api/drift` REST API. This slice is read/analyze/report only: it does not mutate subscriptions/assets, does not send notifications, and does not add infrastructure.

**Tech Stack:** Java 17, Spring Boot 3.3, JDBC/JdbcTemplate, Flyway, H2 tests, MockMvc.

---

## Scope

Build this phase:

- `drift_record` table.
- `POST /api/drift/analyze`.
- `GET /api/drift`.
- Three drift types:
  - `DECLARED_UNUSED`: active subscription has no runtime usage or has not been seen after the unused cutoff.
  - `UNDECLARED_USAGE`: successful query usage exists for an asset/consumer pair without an active subscription for that pair.
  - `STALE_DECLARATION`: active subscription declaration has not been refreshed after the stale cutoff.
- Idempotent analysis: repeated runs refresh existing open records instead of creating duplicates.
- Tests proving all three drift types and idempotency.

Do not build this phase:

- Automatic remediation.
- Notification publishing for drift.
- Drift resolve/ignore APIs.
- Metadata snapshot sync.
- Formal `/rest/oss/inner/modelengineservice/v1` path migration.
- Frontend UI.
- Docker Compose or shared infrastructure changes.

## Current Code Context

Existing tables:

- `data_asset(asset_id, asset_code, ...)`
- `consumer(consumer_id, consumer_name, environment, ...)`
- `subscription(subscription_id, asset_id, consumer_id, status, last_registered_at, last_runtime_seen_at, ...)`
- `query_record(query_id, asset_id, consumer_id, subscription_id, status, created_at, ...)`

Existing API patterns:

- Controllers use `/api/...`.
- Tests use `@SpringBootTest`, `@AutoConfigureMockMvc`, H2, and public APIs for setup.
- Repositories use `JdbcTemplate` and JSON text through Jackson `ObjectMapper`.

Important existing semantics:

- Product/API query with `subscriptionId` updates `subscription.last_runtime_seen_at`.
- SQL/API query records write to `query_record`.
- `SubscriptionStatus.ACTIVE` is the active declaration status.
- `QueryStatus.SUCCESS` is the successful runtime usage status.

## Drift Semantics

### `DECLARED_UNUSED`

A subscription creates a declared-unused drift when:

```sql
s.status = 'ACTIVE'
and (
  s.last_runtime_seen_at is null
  or s.last_runtime_seen_at < :unusedCutoff
)
```

The finding is keyed by:

```text
DECLARED_UNUSED:<subscription_id>
```

Evidence:

```json
{
  "subscriptionId": "sub_x",
  "assetCode": "ads_cell_profile",
  "consumerName": "rno-dashboard",
  "lastRuntimeSeenAt": null,
  "unusedCutoff": "2026-05-13T00:00:00Z"
}
```

### `UNDECLARED_USAGE`

A successful query creates an undeclared-usage drift when:

```sql
q.status = 'SUCCESS'
and q.asset_id is not null
and q.consumer_id is not null
and q.created_at >= :usageSince
and not exists (
  select 1
  from subscription s
  where s.asset_id = q.asset_id
    and s.consumer_id = q.consumer_id
    and s.status = 'ACTIVE'
)
```

The analyzer groups by `asset_id, consumer_id` and creates one finding per pair.

The finding is keyed by:

```text
UNDECLARED_USAGE:<asset_id>:<consumer_id>
```

Evidence:

```json
{
  "assetCode": "ads_cell_profile",
  "consumerName": "ad-hoc-tool",
  "queryCount": 2,
  "firstSeenAt": "2026-06-11T00:00:00Z",
  "lastSeenAt": "2026-06-12T00:00:00Z",
  "usageSince": "2026-05-13T00:00:00Z"
}
```

### `STALE_DECLARATION`

A subscription creates a stale-declaration drift when:

```sql
s.status = 'ACTIVE'
and s.last_registered_at < :staleCutoff
```

The finding is keyed by:

```text
STALE_DECLARATION:<subscription_id>
```

Evidence:

```json
{
  "subscriptionId": "sub_x",
  "assetCode": "ads_cell_profile",
  "consumerName": "rno-dashboard",
  "lastRegisteredAt": "2026-04-01T00:00:00Z",
  "staleCutoff": "2026-05-13T00:00:00Z"
}
```

## API Contract

### `POST /api/drift/analyze`

Request:

```json
{
  "unusedAfterDays": 30,
  "staleAfterDays": 30,
  "usageLookbackDays": 30
}
```

Defaults:

- `unusedAfterDays`: 30
- `staleAfterDays`: 30
- `usageLookbackDays`: 30

Response:

```json
{
  "createdCount": 3,
  "refreshedCount": 0,
  "records": [
    {
      "driftId": "drift_x",
      "driftType": "DECLARED_UNUSED",
      "status": "OPEN",
      "assetCode": "ads_cell_profile",
      "consumerName": "rno-dashboard",
      "subscriptionId": "sub_x",
      "evidence": {},
      "detectedAt": "2026-06-12T00:00:00Z",
      "resolvedAt": null
    }
  ]
}
```

### `GET /api/drift`

Response:

```json
[
  {
    "driftId": "drift_x",
    "driftType": "DECLARED_UNUSED",
    "status": "OPEN",
    "assetCode": "ads_cell_profile",
    "consumerName": "rno-dashboard",
    "subscriptionId": "sub_x",
    "evidence": {},
    "detectedAt": "2026-06-12T00:00:00Z",
    "resolvedAt": null
  }
]
```

Ordering:

```text
detected_at asc, drift_id asc
```

## File Structure

- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/DriftType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/DriftStatus.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/DriftDtos.java`
- Create: `data-gov-platform/data-gov-server/src/main/resources/db/migration/V6__drift_records.sql`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/drift/DriftController.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/drift/DriftService.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/drift/DriftRepository.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/drift/DriftDataAccessException.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/drift/DriftSchemaMigrationTest.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/drift/DriftControllerTest.java`

## Task 1: Drift Contracts And Migration

**Files:**

- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/DriftType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/DriftStatus.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/DriftDtos.java`
- Create: `data-gov-platform/data-gov-server/src/main/resources/db/migration/V6__drift_records.sql`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/drift/DriftSchemaMigrationTest.java`

- [x] **Step 1: Write the failing schema and DTO test**

Create `DriftSchemaMigrationTest.java`:

```java
package io.datagov.server.drift;

import io.datagov.common.dto.DriftDtos;
import io.datagov.common.enums.DriftStatus;
import io.datagov.common.enums.DriftType;
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
class DriftSchemaMigrationTest {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void driftTableAndDtosAreAvailable() {
        Integer tableCount = jdbcTemplate.queryForObject(
                "select count(*) from information_schema.tables where table_name = 'DRIFT_RECORD'",
                Integer.class);

        DriftDtos.DriftRecordResponse record = new DriftDtos.DriftRecordResponse(
                "drift_1",
                DriftType.DECLARED_UNUSED,
                DriftStatus.OPEN,
                "asset_1",
                "ads_cell_profile",
                "consumer_1",
                "rno-dashboard",
                "sub_1",
                Map.of("subscriptionId", "sub_1"),
                Instant.parse("2026-06-12T00:00:00Z"),
                null);
        DriftDtos.DriftAnalysisResponse response = new DriftDtos.DriftAnalysisResponse(
                1,
                0,
                List.of(record));

        assertThat(tableCount).isEqualTo(1);
        assertThat(response.createdCount()).isEqualTo(1);
        assertThat(response.records()).hasSize(1);
        assertThat(response.records().get(0).driftType()).isEqualTo(DriftType.DECLARED_UNUSED);
    }
}
```

- [x] **Step 2: Run the test and verify red**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=DriftSchemaMigrationTest test
```

Expected: fails because `DriftDtos`, `DriftType`, `DriftStatus`, and `drift_record` do not exist.

- [x] **Step 3: Add drift enums and DTOs**

Create `DriftType.java`:

```java
package io.datagov.common.enums;

public enum DriftType {
    DECLARED_UNUSED,
    UNDECLARED_USAGE,
    STALE_DECLARATION
}
```

Create `DriftStatus.java`:

```java
package io.datagov.common.enums;

public enum DriftStatus {
    OPEN,
    IGNORED,
    RESOLVED
}
```

Create `DriftDtos.java`:

```java
package io.datagov.common.dto;

import io.datagov.common.enums.DriftStatus;
import io.datagov.common.enums.DriftType;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class DriftDtos {
    private DriftDtos() {
    }

    public record AnalyzeDriftRequest(
            Integer unusedAfterDays,
            Integer staleAfterDays,
            Integer usageLookbackDays
    ) {
    }

    public record DriftRecordResponse(
            String driftId,
            DriftType driftType,
            DriftStatus status,
            String assetId,
            String assetCode,
            String consumerId,
            String consumerName,
            String subscriptionId,
            Map<String, Object> evidence,
            Instant detectedAt,
            Instant resolvedAt
    ) {
    }

    public record DriftAnalysisResponse(
            int createdCount,
            int refreshedCount,
            List<DriftRecordResponse> records
    ) {
    }
}
```

- [x] **Step 4: Add V6 drift migration**

Create `V6__drift_records.sql`:

```sql
create table drift_record (
    drift_id varchar(64) primary key,
    drift_type varchar(64) not null,
    asset_id varchar(64) references data_asset(asset_id) on delete set null,
    consumer_id varchar(64) references consumer(consumer_id) on delete set null,
    subscription_id varchar(64) references subscription(subscription_id) on delete set null,
    unique_key varchar(256) not null unique,
    evidence text,
    status varchar(32) not null,
    detected_at timestamp not null,
    resolved_at timestamp
);

create index idx_drift_record_type on drift_record(drift_type);
create index idx_drift_record_status on drift_record(status);
create index idx_drift_record_asset_id on drift_record(asset_id);
create index idx_drift_record_consumer_id on drift_record(consumer_id);
create index idx_drift_record_subscription_id on drift_record(subscription_id);
create index idx_drift_record_detected_at on drift_record(detected_at);
```

- [x] **Step 5: Run the focused schema test**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=DriftSchemaMigrationTest test
```

Expected: `BUILD SUCCESS`.

## Task 2: Drift Controller Tests

**Files:**

- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/drift/DriftControllerTest.java`

- [x] **Step 1: Write failing drift API tests**

Create `DriftControllerTest.java`:

```java
package io.datagov.server.drift;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.sql.Timestamp;
import java.time.Instant;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class DriftControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void analyzeCreatesDeclaredUnusedDriftForActiveSubscriptionWithNoRuntimeUsage() throws Exception {
        registerAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard");

        mockMvc.perform(post("/api/drift/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "unusedAfterDays": 30,
                                  "staleAfterDays": 365,
                                  "usageLookbackDays": 30
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1))
                .andExpect(jsonPath("$.refreshedCount").value(0))
                .andExpect(jsonPath("$.records", hasSize(1)))
                .andExpect(jsonPath("$.records[0].driftType").value("DECLARED_UNUSED"))
                .andExpect(jsonPath("$.records[0].status").value("OPEN"))
                .andExpect(jsonPath("$.records[0].assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.records[0].consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.records[0].evidence.subscriptionId").exists());
    }

    @Test
    void analyzeCreatesUndeclaredUsageDriftForSuccessfulQueryWithoutActiveSubscription() throws Exception {
        registerAsset("ads_cell_profile");
        insertConsumer("consumer_ad_hoc", "ad-hoc-tool", "prod");
        insertSuccessfulQuery("query_1", assetId("ads_cell_profile"), "consumer_ad_hoc", Instant.now());

        mockMvc.perform(post("/api/drift/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "unusedAfterDays": 30,
                                  "staleAfterDays": 365,
                                  "usageLookbackDays": 30
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1))
                .andExpect(jsonPath("$.records[0].driftType").value("UNDECLARED_USAGE"))
                .andExpect(jsonPath("$.records[0].assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.records[0].consumerName").value("ad-hoc-tool"))
                .andExpect(jsonPath("$.records[0].evidence.queryCount").value(1));
    }

    @Test
    void analyzeCreatesStaleDeclarationDriftForOldActiveSubscription() throws Exception {
        registerAsset("ads_cell_profile");
        String subscriptionId = createSubscription("ads_cell_profile", "rno-dashboard");
        jdbcTemplate.update(
                "update subscription set last_registered_at = ?, last_runtime_seen_at = ? where subscription_id = ?",
                Timestamp.from(Instant.parse("2026-04-01T00:00:00Z")),
                Timestamp.from(Instant.now()),
                subscriptionId);

        mockMvc.perform(post("/api/drift/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "unusedAfterDays": 365,
                                  "staleAfterDays": 30,
                                  "usageLookbackDays": 30
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1))
                .andExpect(jsonPath("$.records[0].driftType").value("STALE_DECLARATION"))
                .andExpect(jsonPath("$.records[0].subscriptionId").value(subscriptionId))
                .andExpect(jsonPath("$.records[0].evidence.staleCutoff").exists());
    }

    @Test
    void repeatedAnalyzeRefreshesExistingOpenDriftWithoutDuplicates() throws Exception {
        registerAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard");

        String request = """
                {
                  "unusedAfterDays": 30,
                  "staleAfterDays": 365,
                  "usageLookbackDays": 30
                }
                """;

        mockMvc.perform(post("/api/drift/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1))
                .andExpect(jsonPath("$.refreshedCount").value(0));

        mockMvc.perform(post("/api/drift/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(0))
                .andExpect(jsonPath("$.refreshedCount").value(1));

        mockMvc.perform(get("/api/drift"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].driftType").value("DECLARED_UNUSED"));
    }

    private void registerAsset(String assetCode) throws Exception {
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "%s",
                                  "assetName": "%s",
                                  "assetType": "TABLE",
                                  "engine": "STARROCKS",
                                  "lifecycleStatus": "ACTIVE",
                                  "queryable": true,
                                  "federatedQueryable": true
                                }
                                """.formatted(assetCode, assetCode)))
                .andExpect(status().isOk());
    }

    private String createSubscription(String assetCode, String consumerName) throws Exception {
        String response = mockMvc.perform(post("/api/assets/{assetCode}/subscriptions", assetCode)
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
                                    "purpose": "dashboard display",
                                    "notifyOn": ["SCHEMA_CHANGE"]
                                  }
                                }
                                """.formatted(consumerName, assetCode)))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();
        return com.jayway.jsonpath.JsonPath.read(response, "$.subscriptionId");
    }

    private String assetId(String assetCode) {
        return jdbcTemplate.queryForObject(
                "select asset_id from data_asset where asset_code = ?",
                String.class,
                assetCode);
    }

    private void insertConsumer(String consumerId, String consumerName, String environment) {
        Instant now = Instant.now();
        jdbcTemplate.update("""
                insert into consumer (
                    consumer_id, consumer_type, consumer_name, environment, created_at, updated_at
                ) values (?, 'MICROSERVICE', ?, ?, ?, ?)
                """,
                consumerId,
                consumerName,
                environment,
                Timestamp.from(now),
                Timestamp.from(now));
    }

    private void insertSuccessfulQuery(String queryId, String assetId, String consumerId, Instant createdAt) {
        jdbcTemplate.update("""
                insert into query_record (
                    query_id, request_type, asset_id, consumer_id, status, created_at
                ) values (?, 'PRODUCT_API', ?, ?, 'SUCCESS', ?)
                """,
                queryId,
                assetId,
                consumerId,
                Timestamp.from(createdAt));
    }
}
```

- [x] **Step 2: Run tests and verify red**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=DriftControllerTest test
```

Expected: fails because `DriftController` and drift service implementation do not exist.

## Task 3: Drift Repository And Service

**Files:**

- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/drift/DriftRepository.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/drift/DriftService.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/drift/DriftDataAccessException.java`

- [x] **Step 1: Add data access exception**

Create `DriftDataAccessException.java`:

```java
package io.datagov.server.drift;

public class DriftDataAccessException extends RuntimeException {
    public DriftDataAccessException(String message, Throwable cause) {
        super(message, cause);
    }
}
```

- [x] **Step 2: Implement repository skeleton and row mapping**

Create `DriftRepository.java` with these public methods:

```java
package io.datagov.server.drift;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.dto.DriftDtos;
import io.datagov.common.enums.DriftStatus;
import io.datagov.common.enums.DriftType;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public class DriftRepository {
    private static final TypeReference<Map<String, Object>> EVIDENCE_TYPE = new TypeReference<>() {
    };

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public DriftRepository(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public List<DriftCandidate> findDeclaredUnusedCandidates(Instant unusedCutoff) {
        return jdbcTemplate.query("""
                select s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name,
                       s.last_runtime_seen_at, s.last_registered_at, count(q.query_id) as query_count,
                       min(q.created_at) as first_seen_at, max(q.created_at) as last_seen_at
                from subscription s
                join data_asset a on a.asset_id = s.asset_id
                join consumer c on c.consumer_id = s.consumer_id
                left join query_record q on q.subscription_id = s.subscription_id and q.status = 'SUCCESS'
                where s.status = 'ACTIVE'
                  and (s.last_runtime_seen_at is null or s.last_runtime_seen_at < ?)
                group by s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name,
                         s.last_runtime_seen_at, s.last_registered_at
                order by s.created_at, s.subscription_id
                """, candidateMapper(), Timestamp.from(unusedCutoff));
    }

    public List<DriftCandidate> findUndeclaredUsageCandidates(Instant usageSince) {
        return jdbcTemplate.query("""
                select null as subscription_id, q.asset_id, a.asset_code, q.consumer_id, c.consumer_name,
                       null as last_runtime_seen_at, null as last_registered_at, count(q.query_id) as query_count,
                       min(q.created_at) as first_seen_at, max(q.created_at) as last_seen_at
                from query_record q
                join data_asset a on a.asset_id = q.asset_id
                join consumer c on c.consumer_id = q.consumer_id
                where q.status = 'SUCCESS'
                  and q.asset_id is not null
                  and q.consumer_id is not null
                  and q.created_at >= ?
                  and not exists (
                      select 1
                      from subscription s
                      where s.asset_id = q.asset_id
                        and s.consumer_id = q.consumer_id
                        and s.status = 'ACTIVE'
                  )
                group by q.asset_id, a.asset_code, q.consumer_id, c.consumer_name
                order by a.asset_code, c.consumer_name
                """, candidateMapper(), Timestamp.from(usageSince));
    }

    public List<DriftCandidate> findStaleDeclarationCandidates(Instant staleCutoff) {
        return jdbcTemplate.query("""
                select s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name,
                       s.last_runtime_seen_at, s.last_registered_at, count(q.query_id) as query_count,
                       min(q.created_at) as first_seen_at, max(q.created_at) as last_seen_at
                from subscription s
                join data_asset a on a.asset_id = s.asset_id
                join consumer c on c.consumer_id = s.consumer_id
                left join query_record q on q.subscription_id = s.subscription_id and q.status = 'SUCCESS'
                where s.status = 'ACTIVE'
                  and s.last_registered_at < ?
                group by s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name,
                         s.last_runtime_seen_at, s.last_registered_at
                order by s.created_at, s.subscription_id
                """, candidateMapper(), Timestamp.from(staleCutoff));
    }

    public Optional<DriftDtos.DriftRecordResponse> findOpenByUniqueKey(String uniqueKey) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select d.drift_id, d.drift_type, d.status, d.asset_id, a.asset_code,
                           d.consumer_id, c.consumer_name, d.subscription_id, d.evidence,
                           d.detected_at, d.resolved_at
                    from drift_record d
                    left join data_asset a on a.asset_id = d.asset_id
                    left join consumer c on c.consumer_id = d.consumer_id
                    where d.unique_key = ? and d.status = 'OPEN'
                    """, driftMapper(), uniqueKey));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    public DriftDtos.DriftRecordResponse insertOpen(
            String driftId,
            DriftType driftType,
            DriftCandidate candidate,
            String uniqueKey,
            Map<String, Object> evidence,
            Instant detectedAt
    ) {
        jdbcTemplate.update("""
                insert into drift_record (
                    drift_id, drift_type, asset_id, consumer_id, subscription_id, unique_key,
                    evidence, status, detected_at, resolved_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                driftId,
                driftType.name(),
                candidate.assetId(),
                candidate.consumerId(),
                candidate.subscriptionId(),
                uniqueKey,
                writeEvidence(evidence),
                DriftStatus.OPEN.name(),
                Timestamp.from(detectedAt),
                null);
        return findOpenByUniqueKey(uniqueKey).orElseThrow();
    }

    public DriftDtos.DriftRecordResponse refreshOpen(
            String uniqueKey,
            Map<String, Object> evidence,
            Instant detectedAt
    ) {
        jdbcTemplate.update("""
                update drift_record
                set evidence = ?, detected_at = ?
                where unique_key = ? and status = 'OPEN'
                """, writeEvidence(evidence), Timestamp.from(detectedAt), uniqueKey);
        return findOpenByUniqueKey(uniqueKey).orElseThrow();
    }

    public List<DriftDtos.DriftRecordResponse> listRecords() {
        return jdbcTemplate.query("""
                select d.drift_id, d.drift_type, d.status, d.asset_id, a.asset_code,
                       d.consumer_id, c.consumer_name, d.subscription_id, d.evidence,
                       d.detected_at, d.resolved_at
                from drift_record d
                left join data_asset a on a.asset_id = d.asset_id
                left join consumer c on c.consumer_id = d.consumer_id
                order by d.detected_at, d.drift_id
                """, driftMapper());
    }

    private RowMapper<DriftCandidate> candidateMapper() {
        return (rs, rowNum) -> new DriftCandidate(
                rs.getString("subscription_id"),
                rs.getString("asset_id"),
                rs.getString("asset_code"),
                rs.getString("consumer_id"),
                rs.getString("consumer_name"),
                rs.getTimestamp("last_runtime_seen_at") == null ? null : rs.getTimestamp("last_runtime_seen_at").toInstant(),
                rs.getTimestamp("last_registered_at") == null ? null : rs.getTimestamp("last_registered_at").toInstant(),
                rs.getLong("query_count"),
                rs.getTimestamp("first_seen_at") == null ? null : rs.getTimestamp("first_seen_at").toInstant(),
                rs.getTimestamp("last_seen_at") == null ? null : rs.getTimestamp("last_seen_at").toInstant());
    }

    private RowMapper<DriftDtos.DriftRecordResponse> driftMapper() {
        return (rs, rowNum) -> new DriftDtos.DriftRecordResponse(
                rs.getString("drift_id"),
                DriftType.valueOf(rs.getString("drift_type")),
                DriftStatus.valueOf(rs.getString("status")),
                rs.getString("asset_id"),
                rs.getString("asset_code"),
                rs.getString("consumer_id"),
                rs.getString("consumer_name"),
                rs.getString("subscription_id"),
                readEvidence(rs.getString("evidence")),
                rs.getTimestamp("detected_at").toInstant(),
                rs.getTimestamp("resolved_at") == null ? null : rs.getTimestamp("resolved_at").toInstant());
    }

    private String writeEvidence(Map<String, Object> evidence) {
        try {
            return objectMapper.writeValueAsString(evidence == null ? Map.of() : evidence);
        } catch (Exception ex) {
            throw new DriftDataAccessException("Failed to serialize drift evidence", ex);
        }
    }

    private Map<String, Object> readEvidence(String evidence) {
        if (evidence == null || evidence.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(evidence, EVIDENCE_TYPE);
        } catch (Exception ex) {
            throw new DriftDataAccessException("Failed to deserialize drift evidence", ex);
        }
    }

    public record DriftCandidate(
            String subscriptionId,
            String assetId,
            String assetCode,
            String consumerId,
            String consumerName,
            Instant lastRuntimeSeenAt,
            Instant lastRegisteredAt,
            long queryCount,
            Instant firstSeenAt,
            Instant lastSeenAt
    ) {
    }
}
```

- [x] **Step 3: Implement drift service**

Create `DriftService.java`:

```java
package io.datagov.server.drift;

import io.datagov.common.dto.DriftDtos;
import io.datagov.common.enums.DriftType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class DriftService {
    private final DriftRepository driftRepository;
    private final TransactionTemplate transactionTemplate;

    public DriftService(DriftRepository driftRepository, TransactionTemplate transactionTemplate) {
        this.driftRepository = driftRepository;
        this.transactionTemplate = transactionTemplate;
    }

    public DriftDtos.DriftAnalysisResponse analyze(DriftDtos.AnalyzeDriftRequest request) {
        Instant now = Instant.now();
        int unusedAfterDays = positiveOrDefault(request == null ? null : request.unusedAfterDays(), 30);
        int staleAfterDays = positiveOrDefault(request == null ? null : request.staleAfterDays(), 30);
        int usageLookbackDays = positiveOrDefault(request == null ? null : request.usageLookbackDays(), 30);
        Instant unusedCutoff = now.minus(unusedAfterDays, ChronoUnit.DAYS);
        Instant staleCutoff = now.minus(staleAfterDays, ChronoUnit.DAYS);
        Instant usageSince = now.minus(usageLookbackDays, ChronoUnit.DAYS);

        return transactionTemplate.execute(status -> {
            ResultAccumulator accumulator = new ResultAccumulator();
            for (DriftRepository.DriftCandidate candidate
                    : driftRepository.findDeclaredUnusedCandidates(unusedCutoff)) {
                accumulator.add(upsert(
                        DriftType.DECLARED_UNUSED,
                        "DECLARED_UNUSED:" + candidate.subscriptionId(),
                        candidate,
                        declaredUnusedEvidence(candidate, unusedCutoff),
                        now));
            }
            for (DriftRepository.DriftCandidate candidate
                    : driftRepository.findUndeclaredUsageCandidates(usageSince)) {
                accumulator.add(upsert(
                        DriftType.UNDECLARED_USAGE,
                        "UNDECLARED_USAGE:" + candidate.assetId() + ":" + candidate.consumerId(),
                        candidate,
                        undeclaredUsageEvidence(candidate, usageSince),
                        now));
            }
            for (DriftRepository.DriftCandidate candidate
                    : driftRepository.findStaleDeclarationCandidates(staleCutoff)) {
                accumulator.add(upsert(
                        DriftType.STALE_DECLARATION,
                        "STALE_DECLARATION:" + candidate.subscriptionId(),
                        candidate,
                        staleDeclarationEvidence(candidate, staleCutoff),
                        now));
            }
            return new DriftDtos.DriftAnalysisResponse(
                    accumulator.createdCount,
                    accumulator.refreshedCount,
                    List.copyOf(accumulator.records));
        });
    }

    public List<DriftDtos.DriftRecordResponse> listRecords() {
        return driftRepository.listRecords();
    }

    private UpsertResult upsert(
            DriftType driftType,
            String uniqueKey,
            DriftRepository.DriftCandidate candidate,
            Map<String, Object> evidence,
            Instant now
    ) {
        return driftRepository.findOpenByUniqueKey(uniqueKey)
                .map(existing -> new UpsertResult(
                        false,
                        driftRepository.refreshOpen(uniqueKey, evidence, now)))
                .orElseGet(() -> new UpsertResult(
                        true,
                        driftRepository.insertOpen(newId(), driftType, candidate, uniqueKey, evidence, now)));
    }

    private Map<String, Object> declaredUnusedEvidence(
            DriftRepository.DriftCandidate candidate,
            Instant unusedCutoff
    ) {
        Map<String, Object> evidence = baseEvidence(candidate);
        evidence.put("lastRuntimeSeenAt", iso(candidate.lastRuntimeSeenAt()));
        evidence.put("unusedCutoff", iso(unusedCutoff));
        return Map.copyOf(evidence);
    }

    private Map<String, Object> undeclaredUsageEvidence(
            DriftRepository.DriftCandidate candidate,
            Instant usageSince
    ) {
        Map<String, Object> evidence = baseEvidence(candidate);
        evidence.put("queryCount", candidate.queryCount());
        evidence.put("firstSeenAt", iso(candidate.firstSeenAt()));
        evidence.put("lastSeenAt", iso(candidate.lastSeenAt()));
        evidence.put("usageSince", iso(usageSince));
        return Map.copyOf(evidence);
    }

    private Map<String, Object> staleDeclarationEvidence(
            DriftRepository.DriftCandidate candidate,
            Instant staleCutoff
    ) {
        Map<String, Object> evidence = baseEvidence(candidate);
        evidence.put("lastRegisteredAt", iso(candidate.lastRegisteredAt()));
        evidence.put("staleCutoff", iso(staleCutoff));
        return Map.copyOf(evidence);
    }

    private Map<String, Object> baseEvidence(DriftRepository.DriftCandidate candidate) {
        Map<String, Object> evidence = new LinkedHashMap<>();
        if (candidate.subscriptionId() != null) {
            evidence.put("subscriptionId", candidate.subscriptionId());
        }
        evidence.put("assetCode", candidate.assetCode());
        evidence.put("consumerName", candidate.consumerName());
        return evidence;
    }

    private int positiveOrDefault(Integer value, int defaultValue) {
        return value == null || value <= 0 ? defaultValue : value;
    }

    private String iso(Instant instant) {
        return instant == null ? null : instant.toString();
    }

    private String newId() {
        return "drift_" + UUID.randomUUID().toString().replace("-", "");
    }

    private static class ResultAccumulator {
        private int createdCount;
        private int refreshedCount;
        private final List<DriftDtos.DriftRecordResponse> records = new ArrayList<>();

        private void add(UpsertResult result) {
            if (result.created()) {
                createdCount++;
            } else {
                refreshedCount++;
            }
            records.add(result.record());
        }
    }

    private record UpsertResult(boolean created, DriftDtos.DriftRecordResponse record) {
    }
}
```

- [x] **Step 4: Run compile-focused tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=DriftSchemaMigrationTest test
```

Expected: `BUILD SUCCESS`.

## Task 4: Drift Controller And Error Mapping

**Files:**

- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/drift/DriftController.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`

- [x] **Step 1: Add drift controller**

Create `DriftController.java`:

```java
package io.datagov.server.drift;

import io.datagov.common.dto.DriftDtos;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/drift")
public class DriftController {
    private final DriftService driftService;

    public DriftController(DriftService driftService) {
        this.driftService = driftService;
    }

    @PostMapping("/analyze")
    public DriftDtos.DriftAnalysisResponse analyze(@RequestBody(required = false) DriftDtos.AnalyzeDriftRequest request) {
        return driftService.analyze(request);
    }

    @GetMapping
    public List<DriftDtos.DriftRecordResponse> listRecords() {
        return driftService.listRecords();
    }
}
```

- [x] **Step 2: Map drift data access errors**

Add import to `ApiExceptionHandler.java`:

```java
import io.datagov.server.drift.DriftDataAccessException;
```

Add this handler near other data access handlers:

```java
    @ExceptionHandler(DriftDataAccessException.class)
    public ResponseEntity<Map<String, Object>> handleDriftDataAccess(DriftDataAccessException ex) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Map.of(
                        "error", "DRIFT_DATA_ACCESS_ERROR",
                        "message", ex.getMessage()));
    }
```

- [x] **Step 3: Run focused drift API tests**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=DriftControllerTest test
```

Expected: `BUILD SUCCESS`.

## Task 5: Full Verification

**Files:**

- Verify all files touched by Tasks 1-4.

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

Expected: no whitespace errors. CRLF conversion warnings are acceptable if exit code is 0.

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

Expected changed files are limited to drift enums/DTOs, drift migration, drift server package, `ApiExceptionHandler`, drift tests, and this plan document.

## Completion Status

Completed on 2026-06-12 on branch `feat/drift-analysis`.

Implemented:

- Drift contracts: `DriftType`, `DriftStatus`, `DriftDtos`.
- Drift schema: `V6__drift_records.sql` with `drift_record` and `unique_key` idempotency.
- Drift analyzer API: `POST /api/drift/analyze`.
- Drift listing API: `GET /api/drift`.
- Drift types: `DECLARED_UNUSED`, `UNDECLARED_USAGE`, `STALE_DECLARATION`.
- Idempotent create/refresh/reopen behavior using repository-level savepoint handling for duplicate-key races.
- Focused schema, controller, repository, and service tests.

Verification:

- `cd data-gov-platform && mvn test`: `BUILD SUCCESS`.
- Server tests: 56 run, 0 failures, 0 errors.
- SDK tests: 15 run, 0 failures, 0 errors.
- `git diff --check`: passed with no output.
- `git status --short -- app-compose.yml docker-compose.yml compose.yaml data-gov-platform\app-compose.yml`: no output.

## Review Checklist

Before merge:

- V6 creates `drift_record` with `unique_key` idempotency.
- `POST /api/drift/analyze` creates all three drift types.
- Repeated analysis refreshes existing open records rather than creating duplicates.
- `GET /api/drift` lists records in stable order.
- Drift analysis does not modify assets, subscriptions, consumers, or query records.
- Drift analysis does not publish Kafka notifications.
- No resolve/ignore API is added.
- No Docker Compose files are changed.

## Plan Self-Review

Spec coverage:

- Drift model: Task 1.
- Declared-unused rule: Task 3.
- Undeclared-usage rule: Task 3.
- Stale-declaration rule: Task 3.
- Analyze/list APIs: Task 4.
- No remediation/notifications/infrastructure: explicitly excluded and checked in Task 5.

Placeholder scan:

- Clean.

Type consistency:

- `DriftType` values match the spec values.
- `DriftStatus.OPEN` is used for new records.
- DTO field names match JSON contract.
- Repository candidate fields match service evidence creation.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-12-drift-analysis.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.
