# StarRocks Query Gateway Implementation Plan

> Scope: implement the first runnable query gateway slice for the Java data governance platform. This phase adds product query API, controlled SQL Gateway, query runtime records, and SDK query helpers. It does not add Docker Compose infrastructure and does not introduce Trino.

## Goal

Expose a unified read path for registered non-Kafka assets:

- Product API: `POST /api/assets/{assetCode}/query`
- SQL Gateway: `POST /api/sql`
- Runtime audit: every query attempt writes `query_record`
- Subscription runtime signal: when a query provides `subscriptionId`, update `subscription.last_runtime_seen_at`
- SDK helper: Java callers can query product assets without hand-building REST requests

StarRocks is the only execution engine for this phase. It reaches Hive, Iceberg, GaussDB, and StarRocks local tables through StarRocks catalogs already provided by shared infrastructure.

## Non-Goals

- No Kafka query support.
- No Trino or additional federation engine.
- No compose or shared infrastructure changes.
- No runtime lifecycle records for Flink/Spark jobs.
- No SQL write support.
- No approval workflow.
- No frontend UI in this phase.

## Current Code Context

Existing Java platform modules:

- `data-gov-common`: shared DTOs and enums.
- `data-gov-server`: Spring Boot server, JDBC repositories, Flyway migrations.
- `data-gov-sdk`: Java SDK and Spring Boot auto-registration.

Existing tables already used by this phase:

- `data_asset`
- `asset_field`
- `asset_physical_binding`
- `consumer`
- `subscription`

Existing asset URLs use `assetCode`, so this phase uses `POST /api/assets/{assetCode}/query` even though the design spec sometimes says `{assetId}`. The service still resolves the stable internal `asset_id` after lookup.

## Data Model

Add Flyway migration:

- `data-gov-platform/data-gov-server/src/main/resources/db/migration/V3__query_records.sql`

Create table `query_record`:

```sql
create table query_record (
    query_id varchar(64) primary key,
    request_type varchar(32) not null,
    asset_id varchar(64) references data_asset(asset_id) on delete set null,
    subscription_id varchar(64) references subscription(subscription_id) on delete set null,
    consumer_id varchar(64) references consumer(consumer_id) on delete set null,
    referenced_asset_codes text,
    selected_fields text,
    filter_json text,
    sql_text text,
    rewritten_sql text,
    status varchar(32) not null,
    error_code varchar(64),
    error_message text,
    row_count integer,
    elapsed_ms bigint,
    created_at timestamp not null
);

create index idx_query_record_created_at on query_record(created_at);
create index idx_query_record_subscription_id on query_record(subscription_id);
create index idx_query_record_consumer_id on query_record(consumer_id);
create index idx_query_record_asset_id on query_record(asset_id);
create index idx_query_record_request_type on query_record(request_type);
```

Use JSON stored as text for `referenced_asset_codes`, `selected_fields`, and `filter_json`, matching the current lightweight JDBC approach.

## Shared DTOs And Enums

Add query DTOs:

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/QueryDtos.java`

Records:

- `AssetQueryRequest`
  - `List<String> select`
  - `List<QueryFilter> filters`
  - `Integer limit`
  - `String subscriptionId`
  - `String consumerName`
  - `String environment`
- `QueryFilter`
  - `String field`
  - `String op`
  - `Object value`
- `SqlQueryRequest`
  - `String sql`
  - `Integer limit`
  - `String subscriptionId`
  - `String consumerName`
  - `String environment`
- `QueryResponse`
  - `String queryId`
  - `List<String> columns`
  - `List<Map<String, Object>> rows`
  - `int rowCount`
  - `long elapsedMs`
- `QueryRecordResponse`
  - optional internal response shape if a query-record lookup is added later. Do not add lookup endpoint in this phase unless tests need it.

Add enums:

- `QueryRequestType`: `PRODUCT_API`, `SQL_GATEWAY`
- `QueryStatus`: `SUCCESS`, `FAILED`

## Server Package Layout

Add package:

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/query`

Classes:

- `QueryController`
- `ProductQueryService`
- `SqlGatewayService`
- `QueryRecordRepository`
- `QueryRecord`
- `StarRocksQueryExecutor`
- `JdbcStarRocksQueryExecutor`
- `StarRocksQueryProperties`
- `StarRocksQueryConfiguration`
- `StarRocksNameResolver`
- `SqlGuard`
- `QueryValidationException`
- `QueryExecutionException`

## StarRocks Execution

Define interface:

```java
public interface StarRocksQueryExecutor {
    QueryResult execute(String sql, List<Object> params, int maxRows, Duration timeout);
}
```

`QueryResult` can be a server-side record with:

- `List<String> columns`
- `List<Map<String, Object>> rows`

Production executor:

- Uses StarRocks MySQL-compatible JDBC URL.
- Add runtime dependency `com.mysql:mysql-connector-j` to `data-gov-server/pom.xml`.
- Configure through properties:

```yaml
data-gov:
  starrocks:
    jdbc-url:
    username:
    password:
    query-timeout-seconds: 30
    default-limit: 100
    max-limit: 5000
```

Bean behavior:

- If `data-gov.starrocks.jdbc-url` is present, create JDBC executor.
- If not present, create a fallback executor that throws a clear `QueryExecutionException` with error code `STARROCKS_NOT_CONFIGURED`.
- Tests override with a fake executor bean.

Do not connect to StarRocks during application startup.

## Product API Behavior

Endpoint:

```http
POST /api/assets/{assetCode}/query
```

Flow:

1. Resolve `data_asset` by `assetCode`.
2. Require `queryable = true`.
3. Reject `engine = KAFKA`.
4. Resolve active `asset_physical_binding`.
5. Require `catalog_name`, `database_name`, and `table_name`.
6. Resolve `asset_field`.
7. Validate selected fields:
   - Empty select means all fields ordered by `ordinal_position`.
   - Non-empty select must be known fields.
8. Validate filters:
   - Field must be known.
   - Operator allowed: `=`, `!=`, `>`, `>=`, `<`, `<=`, `LIKE`, `IN`.
   - `IN` value must be a non-empty list.
9. Clamp limit:
   - Null or non-positive means default limit.
   - Limit greater than max becomes max.
10. Generate parameterized SQL against StarRocks fully qualified name:

```sql
select `field_a`, `field_b`
from `catalog`.`database`.`table`
where `field_c` = ?
limit 100
```

11. Execute through `StarRocksQueryExecutor`.
12. Insert `query_record` with:
   - `request_type = PRODUCT_API`
   - `asset_id`
   - `subscription_id` when supplied
   - referenced asset codes JSON containing the one `assetCode`
   - selected fields JSON
   - filter JSON
   - generated SQL as `rewritten_sql`
   - `SUCCESS` or `FAILED`
13. If `subscriptionId` is present, validate it belongs to the same asset before execution and update `subscription.last_runtime_seen_at` after the attempt is recorded.

## SQL Gateway Behavior

Endpoint:

```http
POST /api/sql
```

Flow:

1. Reject blank SQL.
2. Reject multiple statements.
3. Allow only:
   - `SELECT ...`
   - `WITH ... SELECT ...`
4. Reject write/control keywords:
   - `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `DROP`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`, `CALL`, `LOAD`, `EXPORT`
5. Extract identifiers following `FROM` and `JOIN`.
6. Treat those identifiers as registered `asset_code` values for this phase.
7. Reject unknown assets.
8. Reject Kafka assets.
9. Require `federated_queryable = true` or `queryable = true`. Prefer `federated_queryable` for cross-source joins, but allow single-asset SQL when only `queryable` is true.
10. Resolve active binding for each asset.
11. Replace each asset code in `FROM` and `JOIN` positions with StarRocks three-part name.
12. Apply limit:
    - If request limit is supplied, clamp to max and force that limit.
    - If SQL has no limit, append max limit.
    - If SQL already has a limit and no request limit is supplied, leave it.
13. Execute through `StarRocksQueryExecutor`.
14. Insert `query_record` with:
    - `request_type = SQL_GATEWAY`
    - referenced asset codes JSON
    - original SQL as `sql_text`
    - rewritten SQL as `rewritten_sql`
    - `SUCCESS` or `FAILED`
15. If `subscriptionId` is present, validate it references one of the SQL assets before updating `subscription.last_runtime_seen_at`.

Parser note:

- Use a deliberately narrow first-phase SQL guard and identifier extractor instead of adding a full SQL parser dependency.
- The extractor only supports unqualified asset codes and simple aliasing, for example:

```sql
select a.id, b.score
from ads_cell_profile a
join dwd_session_qos b on a.id = b.cell_id
```

Out of scope for this phase:

- Subqueries with unregistered physical table names.
- Quoted identifiers containing dots.
- Arbitrary StarRocks catalog names in user SQL.

These should fail closed with `QUERY_VALIDATION_ERROR`.

## Error Handling

Extend `ApiExceptionHandler` to handle query exceptions:

- `QueryValidationException` -> `400`
- `QueryExecutionException` -> `503` for not configured/unavailable execution, otherwise `500`

Error response continues using the existing `error`, `message`, `path` shape.

Error codes:

- `ASSET_NOT_QUERYABLE`
- `KAFKA_QUERY_NOT_SUPPORTED`
- `MISSING_PHYSICAL_BINDING`
- `UNKNOWN_FIELD`
- `INVALID_FILTER`
- `INVALID_SQL`
- `UNKNOWN_SQL_ASSET`
- `STARROCKS_NOT_CONFIGURED`
- `QUERY_EXECUTION_FAILED`

Failed queries must still insert `query_record` when the asset or SQL references can be resolved enough to identify intent.

## SDK Additions

Extend `data-gov-sdk` without changing startup registration semantics.

Add convenience API:

```java
QueryResponse result = dataGovClient.asset("ads_cell_profile")
        .select("cell_id", "coverage_score")
        .where("dt", "=", LocalDate.now())
        .limit(100)
        .subscriptionId(subscriptionId)
        .query();
```

Implementation files:

- `DataGovClient`
  - add `AssetQueryBuilder asset(String assetCode)`
  - add `QueryResponse sql(SqlQueryRequest request)`
- `DefaultDataGovClient`
  - implement product query and SQL POST calls
- New SDK builder class:
  - `io.datagov.sdk.AssetQueryBuilder`

Builder rules:

- Keep it immutable or copy-on-write enough that repeated calls do not mutate already-created request objects unexpectedly.
- Use common DTOs.
- Do not introduce Python or Scala SDKs.

## Tests

Add server tests:

- `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/query/QueryControllerTest.java`

Use `@SpringBootTest` + `@AutoConfigureMockMvc` and a `@TestConfiguration` fake `StarRocksQueryExecutor`.

Minimum cases:

1. Product API executes a registered StarRocks asset query and returns rows.
2. Product API records a successful `query_record`.
3. Product API rejects unknown selected field.
4. Product API rejects Kafka asset.
5. Product API validates `subscriptionId` belongs to the queried asset and updates `last_runtime_seen_at`.
6. SQL Gateway rejects `DELETE`.
7. SQL Gateway rewrites registered asset codes to StarRocks three-part names.
8. SQL Gateway supports a simple two-asset join.
9. SQL Gateway rejects unknown asset code.
10. SQL Gateway records failed validation attempts when intent is resolvable.

Add SDK tests:

- `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/DataGovClientQueryTest.java`

Minimum cases:

1. Asset query builder posts to `/api/assets/{assetCode}/query`.
2. SQL helper posts to `/api/sql`.
3. Query failures still throw `DataGovClientException`.

## Implementation Tasks

### Task 1: Common Query DTOs And Migration

Files:

- `data-gov-common/src/main/java/io/datagov/common/dto/QueryDtos.java`
- `data-gov-common/src/main/java/io/datagov/common/enums/QueryRequestType.java`
- `data-gov-common/src/main/java/io/datagov/common/enums/QueryStatus.java`
- `data-gov-server/src/main/resources/db/migration/V3__query_records.sql`

Acceptance:

- Maven compile passes for common/server.
- Flyway migration works with H2 tests.
- No changes to compose files.

### Task 2: Server Query Core

Files:

- `data-gov-server/src/main/java/io/datagov/server/query/*`
- `data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`
- `data-gov-server/pom.xml`
- `data-gov-server/src/main/resources/application.yml`

Acceptance:

- `POST /api/assets/{assetCode}/query` implemented.
- `POST /api/sql` implemented.
- Query validation fails closed.
- StarRocks executor is configurable and does not require live StarRocks in tests.
- Query attempts write `query_record`.
- Subscription runtime timestamp updates only when `subscriptionId` is supplied and valid.

### Task 3: SDK Query Helpers

Files:

- `data-gov-sdk/src/main/java/io/datagov/sdk/DataGovClient.java`
- `data-gov-sdk/src/main/java/io/datagov/sdk/DefaultDataGovClient.java`
- `data-gov-sdk/src/main/java/io/datagov/sdk/AssetQueryBuilder.java`
- `data-gov-sdk/src/test/java/io/datagov/sdk/DataGovClientQueryTest.java`

Acceptance:

- Product query builder works with existing SDK configuration.
- SQL request helper works.
- SDK tests prove endpoint paths and request payloads.

### Task 4: Verification And Review

Commands:

```powershell
cd data-gov-platform
mvn test
```

Also run:

```powershell
git diff --check
```

Acceptance:

- Tests pass.
- No whitespace errors.
- No Docker Compose changes.
- Plan and implementation remain consistent with the design spec decisions:
  - StarRocks as federation engine.
  - Product API priority.
  - SQL Gateway read-only.
  - Kafka excluded from unified query.
  - Query facts recorded in `query_record`.

## Subagent Strategy

Use subagent-driven development in sequence:

1. Implement Task 1.
2. Review Task 1.
3. Implement Task 2.
4. Review Task 2.
5. Implement Task 3.
6. Review Task 3.
7. Run final verification and integration review.

Do not run parallel implementation agents against the same Java modules because the tasks share DTOs, repositories, and tests.

