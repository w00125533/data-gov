# Formal Lineage API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the formal metadata lineage slice and make it runnable through the project Docker infrastructure.

**Architecture:** Reuse the existing lineage graph storage, traversal, and validation patterns. Extend formal metadata contracts for lineage declarations, add repository support for producer-scoped lineage replacement and field edges, and expose `GET /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}/lineage` as a thin formal facade over lineage services. Package the Spring Boot server as a Docker service in `app-compose.yml` while reusing `../shared-data-infra` for shared infrastructure and keeping this repository limited to application services and volumes.

**Tech Stack:** Java 17, Spring Boot 3.3, Spring MVC, Jakarta Validation, JDBC `JdbcTemplate`, H2/Flyway test and Docker runtime database, MockMvc, Maven, Docker Compose.

---

## Scope

This phase implements:

- Formal snapshot lineage ingestion from `metadataList[].lineage.upstreams[]` and `metadataList[].lineage.downstreams[]`.
- Field mapping ingestion from `metadataList[].lineage.*[].fieldMappings[]`.
- Formal lineage discovery: `GET /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}/lineage`.
- Formal lineage response shape with `metadataId`, `nodes`, table-level `edges`, and `fieldEdges`.
- Docker runtime for `data-gov-platform/data-gov-server` under an explicit `governance` profile in `app-compose.yml`.
- Docker smoke verification for registering metadata and reading formal lineage through the containerized Spring Boot service.

This phase does not add Neo4j, HDFS, YARN, Hive, Kafka, StarRocks, Spark, Prometheus, or Grafana services to this repository. It does not change frontend pages, impact analysis, SDK fluent builders, or notification delivery.

## Docker Runtime Basis

- `../shared-data-infra/compose.yaml` owns the external `shared-data-infra` Docker network and already defines the `neo4j` service under profile `data-gov`.
- `app-compose.yml` already joins application containers to the external `shared-data-infra` network.
- This phase adds only an application service and an application data volume for the Spring Boot governance server.
- The governance server uses `SPRING_PROFILES_ACTIVE=docker` and a container-local H2 file database at `/app/data/data-gov` for local Docker smoke verification.
- Shared infrastructure is validated before runtime smoke with:

```powershell
docker compose -f ../shared-data-infra/compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
docker compose -f app-compose.yml --profile governance config
```

## Existing Code To Preserve

- Existing `/api/lineage/edges`, `/api/assets/{assetCode}/lineage`, and `/api/assets/{assetCode}/impact` routes keep their current request and response shapes.
- Existing `LineageService.getLineage(assetCode, direction, depth)` traversal behavior remains the graph engine for both legacy and formal read paths.
- Existing formal metadata snapshot idempotence must remain: repeated identical snapshots do not bump asset schema version.
- Metadata snapshot remains `FULL` only.

## File Structure

- Create `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageType.java`
  - Formal lineage granularity: `TABLE`, `FIELD`.
- Create `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageTransformType.java`
  - Formal transform source: `DIRECT`, `SQL`, `JOB`, `MANUAL`.
- Modify `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/MetadataDtos.java`
  - Extend `MetadataLineageEdgeRequest` with formal lineage fields and field mappings.
- Create `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/FormalLineageDtos.java`
  - Formal lineage response records.
- Create `data-gov-platform/data-gov-common/src/test/java/io/datagov/common/dto/FormalLineageDtosContractTest.java`
  - Contract tests for formal lineage request and response JSON.
- Modify `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageRepository.java`
  - Add producer-scoped edge deactivation, field-edge insert, and field-edge read methods.
- Modify `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageService.java`
  - Add snapshot lineage replacement and formal metadata lineage response mapping.
- Modify `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataService.java`
  - Invoke snapshot lineage replacement after metadata items are upserted.
- Modify `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataController.java`
  - Add `GET /metadata/{metadataId}/lineage`.
- Modify `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/metadata/MetadataControllerTest.java`
  - Add formal snapshot lineage ingestion and formal metadata lineage read tests.
- Modify `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/lineage/LineageControllerTest.java`
  - Add one regression check proving legacy lineage graph still reads table edges after repository changes.
- Modify `data-gov-platform/data-gov-server/pom.xml`
  - Make H2 available at runtime for the Docker profile.
- Create `data-gov-platform/data-gov-server/src/main/resources/application-docker.yml`
  - Configure the container-local H2 runtime datasource.
- Create `data-gov-platform/data-gov-server/Dockerfile`
  - Build and run the Spring Boot governance server image.
- Modify `app-compose.yml`
  - Add the `governance-server` application service under profile `governance` and add its data volume.

## Task 1: Formal Lineage Contracts

**Files:**
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageTransformType.java`
- Modify: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/MetadataDtos.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/FormalLineageDtos.java`
- Create: `data-gov-platform/data-gov-common/src/test/java/io/datagov/common/dto/FormalLineageDtosContractTest.java`

- [ ] **Step 1: Add the failing formal lineage contract test**

Create `data-gov-platform/data-gov-common/src/test/java/io/datagov/common/dto/FormalLineageDtosContractTest.java`:

```java
package io.datagov.common.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.enums.LineageDirection;
import io.datagov.common.enums.LineageTransformType;
import io.datagov.common.enums.LineageType;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class FormalLineageDtosContractTest {
    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

    @Test
    void metadataLineageDeclarationDeserializesFormalFields() throws Exception {
        MetadataDtos.MetadataLineageEdgeRequest request = objectMapper.readValue("""
                {
                  "assetCode": "dwd_cell_profile",
                  "lineageType": "FIELD",
                  "transformType": "SQL",
                  "expression": "case when rsrp_avg >= -95 then 100 else 60 end",
                  "processName": "rno-profile-etl",
                  "jobName": "cell-profile-daily",
                  "fieldMappings": [
                    {
                      "sourceField": "rsrp_avg",
                      "targetField": "coverage_score",
                      "expression": "case when rsrp_avg >= -95 then 100 else 60 end"
                    }
                  ]
                }
                """, MetadataDtos.MetadataLineageEdgeRequest.class);

        assertThat(request.assetCode()).isEqualTo("dwd_cell_profile");
        assertThat(request.lineageType()).isEqualTo(LineageType.FIELD);
        assertThat(request.transformType()).isEqualTo(LineageTransformType.SQL);
        assertThat(request.processName()).isEqualTo("rno-profile-etl");
        assertThat(request.fieldMappings()).hasSize(1);
        assertThat(request.fieldMappings().get(0).sourceField()).isEqualTo("rsrp_avg");
        assertThat(request.fieldMappings().get(0).targetField()).isEqualTo("coverage_score");
    }

    @Test
    void formalLineageResponseSerializesMetadataIdsAndFieldEdges() throws Exception {
        FormalLineageDtos.FormalLineageResponse response = new FormalLineageDtos.FormalLineageResponse(
                "metadata_001",
                LineageDirection.UP,
                5,
                List.of(new FormalLineageDtos.FormalLineageNode(
                        "metadata_000",
                        "dwd_cell_profile",
                        "DWD Cell Profile")),
                List.of(new FormalLineageDtos.FormalLineageEdge(
                        "metadata_000",
                        "dwd_cell_profile",
                        "metadata_001",
                        "ads_cell_profile",
                        LineageType.TABLE,
                        LineageDirection.UP,
                        "job:rno-profile-etl")),
                List.of(new FormalLineageDtos.FormalFieldLineageEdge(
                        "metadata_000",
                        "dwd_cell_profile",
                        "rsrp_avg",
                        "metadata_001",
                        "ads_cell_profile",
                        "coverage_score",
                        LineageType.FIELD,
                        LineageDirection.UP,
                        "case when rsrp_avg >= -95 then 100 else 60 end")));

        String json = objectMapper.writeValueAsString(response);

        assertThat(json).contains("\"metadataId\":\"metadata_001\"");
        assertThat(json).contains("\"sourceMetadataId\":\"metadata_000\"");
        assertThat(json).contains("\"targetField\":\"coverage_score\"");
        assertThat(json).contains("\"lineageType\":\"FIELD\"");
    }
}
```

- [ ] **Step 2: Run the common module test and confirm it fails**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-common -Dtest=FormalLineageDtosContractTest test
```

Expected: compilation fails because `LineageType`, `LineageTransformType`, `FormalLineageDtos`, and extended lineage request fields do not exist.

- [ ] **Step 3: Add lineage enums**

Create `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageType.java`:

```java
package io.datagov.common.enums;

public enum LineageType {
    TABLE,
    FIELD
}
```

Create `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageTransformType.java`:

```java
package io.datagov.common.enums;

public enum LineageTransformType {
    DIRECT,
    SQL,
    JOB,
    MANUAL
}
```

- [ ] **Step 4: Extend `MetadataDtos` lineage request records**

Add imports to `MetadataDtos.java`:

```java
import io.datagov.common.enums.LineageTransformType;
import io.datagov.common.enums.LineageType;
```

Replace `MetadataLineageEdgeRequest` and add `MetadataFieldMappingRequest`:

```java
public record MetadataLineageEdgeRequest(
        @NotBlank String assetCode,
        LineageType lineageType,
        LineageTransformType transformType,
        String expression,
        String processName,
        String jobName,
        @Valid List<MetadataFieldMappingRequest> fieldMappings
) {
}

public record MetadataFieldMappingRequest(
        @NotBlank String sourceField,
        @NotBlank String targetField,
        String expression
) {
}
```

- [ ] **Step 5: Add formal lineage response DTOs**

Create `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/FormalLineageDtos.java`:

```java
package io.datagov.common.dto;

import io.datagov.common.enums.LineageDirection;
import io.datagov.common.enums.LineageType;

import java.util.List;

public final class FormalLineageDtos {
    private FormalLineageDtos() {
    }

    public record FormalLineageNode(
            String metadataId,
            String assetCode,
            String assetName
    ) {
    }

    public record FormalLineageEdge(
            String sourceMetadataId,
            String sourceAssetCode,
            String targetMetadataId,
            String targetAssetCode,
            LineageType lineageType,
            LineageDirection direction,
            String expression
    ) {
    }

    public record FormalFieldLineageEdge(
            String sourceMetadataId,
            String sourceAssetCode,
            String sourceField,
            String targetMetadataId,
            String targetAssetCode,
            String targetField,
            LineageType lineageType,
            LineageDirection direction,
            String expression
    ) {
    }

    public record FormalLineageResponse(
            String metadataId,
            LineageDirection direction,
            int depth,
            List<FormalLineageNode> nodes,
            List<FormalLineageEdge> edges,
            List<FormalFieldLineageEdge> fieldEdges
    ) {
    }
}
```

- [ ] **Step 6: Run the common module test and commit**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-common -Dtest=FormalLineageDtosContractTest test
```

Expected: `BUILD SUCCESS`.

Commit:

```powershell
git add data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageType.java `
        data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LineageTransformType.java `
        data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/MetadataDtos.java `
        data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/FormalLineageDtos.java `
        data-gov-platform/data-gov-common/src/test/java/io/datagov/common/dto/FormalLineageDtosContractTest.java
git commit -m "Add formal lineage contracts"
```

## Task 2: Lineage Repository Field Edge Support

**Files:**
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageRepository.java`

- [ ] **Step 1: Add repository support for replacing snapshot-owned lineage**

Add these public methods after `insertEdge(...)`:

```java
public void deactivateProducerEdgesForAssets(List<String> assetIds, String producer, Instant now) {
    if (assetIds == null || assetIds.isEmpty()) {
        return;
    }
    String placeholders = placeholders(assetIds.size());
    Object[] args = new Object[assetIds.size() + assetIds.size() + 3];
    int index = 0;
    args[index++] = Timestamp.from(now);
    args[index++] = producer;
    for (String assetId : assetIds) {
        args[index++] = assetId;
    }
    for (String assetId : assetIds) {
        args[index++] = assetId;
    }
    try {
        jdbcTemplate.update("""
                update lineage_edge
                set active = false, updated_at = ?
                where producer = ?
                  and active = true
                  and (source_asset_id in (%s) or target_asset_id in (%s))
                """.formatted(placeholders, placeholders), args);
    } catch (DataAccessException ex) {
        throw new LineageDataAccessException("Failed to deactivate producer lineage edges", ex);
    }
}

public void insertFieldEdge(FieldLineageRecord fieldEdge) {
    try {
        jdbcTemplate.update("""
                insert into lineage_field_edge (
                    field_edge_id, lineage_edge_id, source_field_id, target_field_id,
                    transform_expression, description, properties, active, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                fieldEdge.fieldEdgeId(),
                fieldEdge.lineageEdgeId(),
                fieldEdge.sourceFieldId(),
                fieldEdge.targetFieldId(),
                fieldEdge.transformExpression(),
                fieldEdge.description(),
                writeProperties(fieldEdge.properties()),
                true,
                Timestamp.from(fieldEdge.createdAt()),
                Timestamp.from(fieldEdge.updatedAt()));
    } catch (DataAccessException ex) {
        throw new LineageDataAccessException("Failed to insert lineage field edge", ex);
    }
}
```

- [ ] **Step 2: Add field edge read support**

Add this method after `findActiveIncoming(...)`:

```java
public List<FieldLineageView> findActiveFieldEdgesForLineageIds(List<String> lineageEdgeIds) {
    if (lineageEdgeIds == null || lineageEdgeIds.isEmpty()) {
        return List.of();
    }
    try {
        String placeholders = placeholders(lineageEdgeIds.size());
        return jdbcTemplate.query("""
                select lfe.field_edge_id, lfe.lineage_edge_id, lfe.transform_expression,
                       src_field.field_name as source_field_name,
                       tgt_field.field_name as target_field_name
                from lineage_field_edge lfe
                left join asset_field src_field on src_field.field_id = lfe.source_field_id
                left join asset_field tgt_field on tgt_field.field_id = lfe.target_field_id
                where lfe.active = true and lfe.lineage_edge_id in (%s)
                order by lfe.created_at, lfe.field_edge_id
                """.formatted(placeholders),
                (rs, rowNum) -> new FieldLineageView(
                        rs.getString("field_edge_id"),
                        rs.getString("lineage_edge_id"),
                        rs.getString("source_field_name"),
                        rs.getString("target_field_name"),
                        rs.getString("transform_expression")),
                lineageEdgeIds.toArray());
    } catch (DataAccessException ex) {
        throw new LineageDataAccessException("Failed to read lineage field edges", ex);
    }
}
```

- [ ] **Step 3: Add repository record types**

Add these records near the bottom of `LineageRepository`, before private helpers:

```java
public record FieldLineageRecord(
        String fieldEdgeId,
        String lineageEdgeId,
        String sourceFieldId,
        String targetFieldId,
        String transformExpression,
        String description,
        Map<String, Object> properties,
        Instant createdAt,
        Instant updatedAt
) {
}

public record FieldLineageView(
        String fieldEdgeId,
        String lineageEdgeId,
        String sourceField,
        String targetField,
        String expression
) {
}
```

- [ ] **Step 4: Run legacy lineage tests and commit**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=LineageControllerTest test
```

Expected: `BUILD SUCCESS`.

Commit:

```powershell
git add data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageRepository.java
git commit -m "Add lineage field edge repository support"
```

## Task 3: Snapshot Lineage Replacement Service

**Files:**
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageService.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataService.java`
- Modify: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/metadata/MetadataControllerTest.java`

- [ ] **Step 1: Add failing snapshot lineage ingestion test**

Append this test to `MetadataControllerTest`:

```java
@Test
void snapshotRegisterReplacesDeclaredLineageForProducerScope() throws Exception {
    mockMvc.perform(post(BASE_PATH + "/metadata/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(snapshotWithItem(upstreamAndTargetItems("""
                            "lineage": {
                              "upstreams": [
                                {
                                  "assetCode": "dwd_cell_profile",
                                  "lineageType": "FIELD",
                                  "transformType": "SQL",
                                  "expression": "job:rno-profile-etl",
                                  "processName": "rno-profile-etl",
                                  "jobName": "cell-profile-daily",
                                  "fieldMappings": [
                                    {
                                      "sourceField": "rsrp_avg",
                                      "targetField": "coverage_score",
                                      "expression": "case when rsrp_avg >= -95 then 100 else 60 end"
                                    }
                                  ]
                                }
                              ]
                            }
                            """))))
            .andExpect(status().isOk());

    assertThat(activeLineageEdgeCount("dwd_cell_profile", "ads_cell_profile")).isEqualTo(1);
    assertThat(activeFieldLineageCount()).isEqualTo(1);

    mockMvc.perform(post(BASE_PATH + "/metadata/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(snapshotWithItem(upstreamAndTargetItems("""
                            "lineage": {
                              "upstreams": []
                            }
                            """))))
            .andExpect(status().isOk());

    assertThat(activeLineageEdgeCount("dwd_cell_profile", "ads_cell_profile")).isEqualTo(0);
}
```

Add helper methods to the test:

```java
private String upstreamAndTargetItems(String targetLineageBlock) {
    return """
            {
              "assetCode": "dwd_cell_profile",
              "assetName": "DWD Cell Profile",
              "metadataType": "TABLE",
              "sourceType": "HIVE",
              "domain": "wireless-rno",
              "owner": "network-team",
              "queryable": true,
              "federatedQueryable": true,
              "schema": [
                {"fieldName": "cell_id", "fieldType": "varchar", "ordinal": 1},
                {"fieldName": "rsrp_avg", "fieldType": "double", "ordinal": 2}
              ],
              "binding": {
                "sourceType": "HIVE",
                "catalog": "hive_catalog",
                "database": "dwd",
                "table": "dwd_cell_profile"
              }
            },
            {
              "assetCode": "ads_cell_profile",
              "assetName": "ADS Cell Profile",
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
                "table": "ads_cell_profile",
                "queryAdapter": "starrocks"
              },
              %s
            }
            """.formatted(targetLineageBlock);
}

private int activeLineageEdgeCount(String sourceAssetCode, String targetAssetCode) {
    return jdbcTemplate.queryForObject("""
            select count(*)
            from lineage_edge le
            join data_asset src on src.asset_id = le.source_asset_id
            join data_asset tgt on tgt.asset_id = le.target_asset_id
            where src.asset_code = ? and tgt.asset_code = ? and le.active = true
            """, Integer.class, sourceAssetCode, targetAssetCode);
}

private int activeFieldLineageCount() {
    return jdbcTemplate.queryForObject(
            "select count(*) from lineage_field_edge where active = true",
            Integer.class);
}
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=MetadataControllerTest#snapshotRegisterReplacesDeclaredLineageForProducerScope test
```

Expected: assertion fails because snapshot lineage declarations are not yet persisted.

- [ ] **Step 3: Add snapshot lineage replacement in `LineageService`**

Add imports:

```java
import io.datagov.common.dto.MetadataDtos;
import io.datagov.common.enums.LineageRelationType;
import io.datagov.common.enums.LineageTransformType;
import io.datagov.common.enums.LineageType;
```

Add this public method:

```java
public void replaceSnapshotLineage(
        MetadataDtos.ProducerRequest producer,
        List<MetadataDtos.MetadataItemRequest> metadataItems,
        Map<String, AssetDtos.AssetResponse> assetsByCode
) {
    Instant now = Instant.now();
    List<String> scopedAssetIds = assetsByCode.values().stream()
            .map(AssetDtos.AssetResponse::assetId)
            .toList();
    lineageRepository.deactivateProducerEdgesForAssets(scopedAssetIds, producer.serviceName(), now);

    for (MetadataDtos.MetadataItemRequest item : metadataItems) {
        AssetDtos.AssetResponse current = assetsByCode.get(item.assetCode());
        if (current == null || item.lineage() == null) {
            continue;
        }
        for (MetadataDtos.MetadataLineageEdgeRequest upstream : safeLineageEdges(item.lineage().upstreams())) {
            AssetDtos.AssetResponse upstreamAsset = requireAssetFromSnapshotOrRepository(upstream.assetCode(), assetsByCode);
            createSnapshotEdge(upstreamAsset, current, producer.serviceName(), upstream, now);
        }
        for (MetadataDtos.MetadataLineageEdgeRequest downstream : safeLineageEdges(item.lineage().downstreams())) {
            AssetDtos.AssetResponse downstreamAsset = requireAssetFromSnapshotOrRepository(downstream.assetCode(), assetsByCode);
            createSnapshotEdge(current, downstreamAsset, producer.serviceName(), downstream, now);
        }
    }
}
```

Add these private helpers:

```java
private List<MetadataDtos.MetadataLineageEdgeRequest> safeLineageEdges(
        List<MetadataDtos.MetadataLineageEdgeRequest> edges
) {
    return edges == null ? List.of() : edges;
}

private AssetDtos.AssetResponse requireAssetFromSnapshotOrRepository(
        String assetCode,
        Map<String, AssetDtos.AssetResponse> assetsByCode
) {
    AssetDtos.AssetResponse asset = assetsByCode.get(assetCode);
    if (asset != null) {
        return asset;
    }
    return requireAsset(assetCode);
}

private void createSnapshotEdge(
        AssetDtos.AssetResponse source,
        AssetDtos.AssetResponse target,
        String producer,
        MetadataDtos.MetadataLineageEdgeRequest request,
        Instant now
) {
    if (source.assetId().equals(target.assetId())) {
        throw new LineageValidationException(
                "INVALID_LINEAGE_EDGE",
                "Lineage edge source and target must be different assets");
    }
    LineageType lineageType = request.lineageType() == null ? LineageType.TABLE : request.lineageType();
    LineageTransformType transformType = request.transformType() == null
            ? LineageTransformType.DIRECT
            : request.transformType();
    LineageDtos.LineageEdgeResponse edge = new LineageDtos.LineageEdgeResponse(
            newId("lin_"),
            toNode(source),
            toNode(target),
            LineageRelationType.DERIVES,
            producer,
            request.processName(),
            request.jobName(),
            request.expression(),
            Map.of(
                    "lineageType", lineageType.name(),
                    "transformType", transformType.name()),
            true,
            now,
            now);
    lineageRepository.insertEdge(edge);

    if (lineageType == LineageType.FIELD) {
        for (MetadataDtos.MetadataFieldMappingRequest mapping : safeFieldMappings(request.fieldMappings())) {
            lineageRepository.insertFieldEdge(new LineageRepository.FieldLineageRecord(
                    newId("lfe_"),
                    edge.edgeId(),
                    requireFieldId(source.assetId(), mapping.sourceField()),
                    requireFieldId(target.assetId(), mapping.targetField()),
                    mapping.expression(),
                    null,
                    Map.of(),
                    now,
                    now));
        }
    }
}

private List<MetadataDtos.MetadataFieldMappingRequest> safeFieldMappings(
        List<MetadataDtos.MetadataFieldMappingRequest> mappings
) {
    return mappings == null ? List.of() : mappings;
}

private String requireFieldId(String assetId, String fieldName) {
    return assetRepository.findFields(assetId).stream()
            .filter(field -> field.fieldName().equals(fieldName))
            .map(AssetDtos.FieldResponse::fieldId)
            .findFirst()
            .orElseThrow(() -> new LineageValidationException(
                    "UNKNOWN_LINEAGE_FIELD",
                    "Unknown lineage field: " + fieldName));
}
```

- [ ] **Step 4: Invoke lineage replacement from `MetadataService`**

Add dependency field and constructor parameter:

```java
private final LineageService lineageService;
```

Constructor parameter:

```java
LineageService lineageService
```

Assign it:

```java
this.lineageService = lineageService;
```

In `registerSnapshotInTransaction`, after the loop that builds `items` and before `markMissingScopedAssetsRemoved(...)`, create an asset map and call lineage replacement:

```java
Map<String, AssetDtos.AssetResponse> assetsByCode = new LinkedHashMap<>();
```

Inside the metadata item loop after `asset` is resolved:

```java
assetsByCode.put(asset.assetCode(), asset);
```

After the loop:

```java
lineageService.replaceSnapshotLineage(request.producer(), request.metadataList(), assetsByCode);
```

Add import:

```java
import io.datagov.server.lineage.LineageService;
```

- [ ] **Step 5: Run metadata and legacy lineage tests and commit**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server "-Dtest=MetadataControllerTest,LineageControllerTest" test
```

Expected: `BUILD SUCCESS`.

Commit:

```powershell
git add data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageService.java `
        data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataService.java `
        data-gov-platform/data-gov-server/src/test/java/io/datagov/server/metadata/MetadataControllerTest.java
git commit -m "Persist formal snapshot lineage"
```

## Task 4: Formal Metadata Lineage Read API

**Files:**
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageService.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataController.java`
- Modify: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/metadata/MetadataControllerTest.java`

- [ ] **Step 1: Add failing formal lineage read tests**

Append this test to `MetadataControllerTest`:

```java
@Test
void formalMetadataLineageReturnsNodesEdgesAndFieldEdgesByMetadataId() throws Exception {
    mockMvc.perform(post(BASE_PATH + "/metadata/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(snapshotWithItem(upstreamAndTargetItems("""
                            "lineage": {
                              "upstreams": [
                                {
                                  "assetCode": "dwd_cell_profile",
                                  "lineageType": "FIELD",
                                  "transformType": "SQL",
                                  "expression": "job:rno-profile-etl",
                                  "fieldMappings": [
                                    {
                                      "sourceField": "rsrp_avg",
                                      "targetField": "coverage_score",
                                      "expression": "case when rsrp_avg >= -95 then 100 else 60 end"
                                    }
                                  ]
                                }
                              ]
                            }
                            """))))
            .andExpect(status().isOk());

    String metadataId = metadataId("ads_cell_profile");
    String upstreamMetadataId = metadataId("dwd_cell_profile");

    mockMvc.perform(get(BASE_PATH + "/metadata/{metadataId}/lineage", metadataId)
                    .param("direction", "up")
                    .param("depth", "5"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.metadataId").value(metadataId))
            .andExpect(jsonPath("$.direction").value("UP"))
            .andExpect(jsonPath("$.depth").value(5))
            .andExpect(jsonPath("$.nodes", hasSize(2)))
            .andExpect(jsonPath("$.nodes[?(@.metadataId == '%s')]".formatted(upstreamMetadataId), hasSize(1)))
            .andExpect(jsonPath("$.edges", hasSize(1)))
            .andExpect(jsonPath("$.edges[0].sourceMetadataId").value(upstreamMetadataId))
            .andExpect(jsonPath("$.edges[0].targetMetadataId").value(metadataId))
            .andExpect(jsonPath("$.edges[0].lineageType").value("FIELD"))
            .andExpect(jsonPath("$.edges[0].expression").value("job:rno-profile-etl"))
            .andExpect(jsonPath("$.fieldEdges", hasSize(1)))
            .andExpect(jsonPath("$.fieldEdges[0].sourceField").value("rsrp_avg"))
            .andExpect(jsonPath("$.fieldEdges[0].targetField").value("coverage_score"));
}

@Test
void formalMetadataLineageMissingMetadataReturns404() throws Exception {
    mockMvc.perform(get(BASE_PATH + "/metadata/{metadataId}/lineage", "missing_metadata"))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
}
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server -Dtest=MetadataControllerTest#formalMetadataLineageReturnsNodesEdgesAndFieldEdgesByMetadataId test
```

Expected: fails with unmapped formal lineage route or missing service method.

- [ ] **Step 3: Add formal lineage response method in `LineageService`**

Add import:

```java
import io.datagov.common.dto.FormalLineageDtos;
import io.datagov.common.enums.LineageType;
```

Add this public method:

```java
public FormalLineageDtos.FormalLineageResponse getFormalMetadataLineage(
        String metadataId,
        String direction,
        int depth
) {
    AssetDtos.AssetResponse asset = assetRepository.findAssetById(metadataId)
            .orElseThrow(() -> new AssetNotFoundException(metadataId));
    LineageDtos.LineageGraphResponse graph = getLineage(asset.assetCode(), direction, depth);
    Map<String, List<LineageRepository.FieldLineageView>> fieldEdgesByLineageId =
            lineageRepository.findActiveFieldEdgesForLineageIds(graph.edges().stream()
                            .map(LineageDtos.LineageEdgeResponse::edgeId)
                            .toList())
                    .stream()
                    .collect(java.util.stream.Collectors.groupingBy(
                            LineageRepository.FieldLineageView::lineageEdgeId,
                            LinkedHashMap::new,
                            java.util.stream.Collectors.toList()));

    List<FormalLineageDtos.FormalLineageEdge> edges = graph.edges().stream()
            .map(edge -> toFormalLineageEdge(edge, graph.direction()))
            .toList();
    List<FormalLineageDtos.FormalFieldLineageEdge> fieldEdges = graph.edges().stream()
            .flatMap(edge -> fieldEdgesByLineageId.getOrDefault(edge.edgeId(), List.of()).stream()
                    .map(fieldEdge -> toFormalFieldLineageEdge(edge, fieldEdge, graph.direction())))
            .toList();

    return new FormalLineageDtos.FormalLineageResponse(
            metadataId,
            graph.direction(),
            graph.depth(),
            graph.nodes().stream().map(this::toFormalLineageNode).toList(),
            edges,
            fieldEdges);
}
```

Add private mapping helpers:

```java
private FormalLineageDtos.FormalLineageNode toFormalLineageNode(LineageDtos.LineageAssetNode node) {
    return new FormalLineageDtos.FormalLineageNode(
            node.assetId(),
            node.assetCode(),
            node.assetName());
}

private FormalLineageDtos.FormalLineageEdge toFormalLineageEdge(
        LineageDtos.LineageEdgeResponse edge,
        LineageDirection direction
) {
    return new FormalLineageDtos.FormalLineageEdge(
            edge.source().assetId(),
            edge.source().assetCode(),
            edge.target().assetId(),
            edge.target().assetCode(),
            lineageType(edge),
            direction,
            edge.description());
}

private FormalLineageDtos.FormalFieldLineageEdge toFormalFieldLineageEdge(
        LineageDtos.LineageEdgeResponse edge,
        LineageRepository.FieldLineageView fieldEdge,
        LineageDirection direction
) {
    return new FormalLineageDtos.FormalFieldLineageEdge(
            edge.source().assetId(),
            edge.source().assetCode(),
            fieldEdge.sourceField(),
            edge.target().assetId(),
            edge.target().assetCode(),
            fieldEdge.targetField(),
            LineageType.FIELD,
            direction,
            fieldEdge.expression());
}

private LineageType lineageType(LineageDtos.LineageEdgeResponse edge) {
    Object value = edge.properties().get("lineageType");
    if (value instanceof String text && !text.isBlank()) {
        return LineageType.valueOf(text);
    }
    return LineageType.TABLE;
}
```

- [ ] **Step 4: Add the formal lineage route to `MetadataController`**

Add import:

```java
import io.datagov.common.dto.FormalLineageDtos;
import io.datagov.server.lineage.LineageService;
```

Add field and constructor parameter:

```java
private final LineageService lineageService;
```

Constructor:

```java
public MetadataController(MetadataService metadataService, LineageService lineageService) {
    this.metadataService = metadataService;
    this.lineageService = lineageService;
}
```

Add endpoint after `getMetadata(...)`:

```java
@GetMapping("/metadata/{metadataId}/lineage")
public FormalLineageDtos.FormalLineageResponse getMetadataLineage(
        @PathVariable("metadataId") String metadataId,
        @RequestParam(name = "direction", defaultValue = "down") String direction,
        @RequestParam(name = "depth", defaultValue = "3") int depth
) {
    return lineageService.getFormalMetadataLineage(metadataId, direction, depth);
}
```

- [ ] **Step 5: Run formal metadata and legacy lineage tests and commit**

Run:

```powershell
cd data-gov-platform
mvn -pl data-gov-server "-Dtest=MetadataControllerTest,LineageControllerTest" test
```

Expected: `BUILD SUCCESS`.

Commit:

```powershell
git add data-gov-platform/data-gov-server/src/main/java/io/datagov/server/lineage/LineageService.java `
        data-gov-platform/data-gov-server/src/main/java/io/datagov/server/metadata/MetadataController.java `
        data-gov-platform/data-gov-server/src/test/java/io/datagov/server/metadata/MetadataControllerTest.java
git commit -m "Add formal metadata lineage API"
```

## Task 5: Docker Governance Server Runtime

**Files:**
- Modify: `data-gov-platform/data-gov-server/pom.xml`
- Create: `data-gov-platform/data-gov-server/src/main/resources/application-docker.yml`
- Create: `data-gov-platform/data-gov-server/Dockerfile`
- Modify: `app-compose.yml`

- [ ] **Step 1: Make H2 available to the packaged server**

In `data-gov-platform/data-gov-server/pom.xml`, replace the H2 dependency block:

```xml
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>test</scope>
        </dependency>
```

with:

```xml
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>
```

- [ ] **Step 2: Add the Docker runtime Spring profile**

Create `data-gov-platform/data-gov-server/src/main/resources/application-docker.yml`:

```yaml
spring:
  datasource:
    url: ${DATAGOV_GAUSSDB_JDBC_URL:jdbc:h2:file:/app/data/data-gov;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH}
    username: ${DATAGOV_GAUSSDB_USER:sa}
    password: ${DATAGOV_GAUSSDB_PASSWORD:}
    driver-class-name: org.h2.Driver
```

- [ ] **Step 3: Add the Spring Boot server Dockerfile**

Create `data-gov-platform/data-gov-server/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.6
FROM maven:3.9.9-eclipse-temurin-17 AS build

WORKDIR /workspace

COPY pom.xml .
COPY data-gov-common/pom.xml data-gov-common/pom.xml
COPY data-gov-server/pom.xml data-gov-server/pom.xml
COPY data-gov-sdk/pom.xml data-gov-sdk/pom.xml

RUN --mount=type=cache,target=/root/.m2 mvn -B -pl data-gov-server -am -DskipTests dependency:go-offline

COPY data-gov-common data-gov-common
COPY data-gov-server data-gov-server
COPY data-gov-sdk data-gov-sdk

RUN --mount=type=cache,target=/root/.m2 mvn -B -pl data-gov-server -am -DskipTests package

FROM eclipse-temurin:17-jre-jammy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home datagov \
    && mkdir -p /app/data \
    && chown -R datagov:datagov /app

COPY --from=build /workspace/data-gov-server/target/data-gov-server-*.jar /app/data-gov-server.jar

USER datagov

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/data-gov-server.jar"]
```

- [ ] **Step 4: Add the governance application service to Compose**

In `app-compose.yml`, add this service after `backend` and before `frontend`:

```yaml
  governance-server:
    profiles: ["governance"]
    build:
      context: ./data-gov-platform
      dockerfile: data-gov-server/Dockerfile
    container_name: data-gov-governance-server
    environment:
      SPRING_PROFILES_ACTIVE: docker
      DATAGOV_GAUSSDB_JDBC_URL: jdbc:h2:file:/app/data/data-gov;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH
      DATAGOV_GAUSSDB_USER: sa
      DATAGOV_GAUSSDB_PASSWORD: ""
      DATA_GOV_KAFKA_BOOTSTRAP_SERVERS: ${DATA_GOV_KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}
    volumes:
      - governance-server-data:/app/data
    ports:
      - "${DATA_GOV_SERVER_PORT:-8080}:8080"
    networks:
      - default
      - shared-data-infra
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8080/actuator/health | grep -q '\"status\":\"UP\"'"]
      interval: 10s
      timeout: 5s
      retries: 30
      start_period: 60s
```

In the `volumes:` block of `app-compose.yml`, add:

```yaml
  governance-server-data:
```

- [ ] **Step 5: Validate shared infrastructure and application Compose files**

Run from repository root:

```powershell
docker compose -f ../shared-data-infra/compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
docker compose -f app-compose.yml --profile governance config
```

Expected: all three commands render valid Compose configuration. The shared config includes the `neo4j` service and `shared-data-infra` network. The profile-enabled app config includes `governance-server`, `governance-server-data`, and the external `shared-data-infra` network.

- [ ] **Step 6: Build and start the Docker runtime**

Run from repository root:

```powershell
docker compose -f ../shared-data-infra/compose.yaml --profile data-gov up -d
docker compose -f app-compose.yml --profile governance up -d --build governance-server
```

Expected: shared infrastructure starts the `neo4j` profile service, and the application compose starts `data-gov-governance-server`.

- [ ] **Step 7: Verify the Spring Boot health endpoint through Docker**

Run:

```powershell
Invoke-RestMethod http://localhost:8080/actuator/health
docker compose -f app-compose.yml --profile governance ps governance-server
```

Expected: health response contains `status` equal to `UP`, and `governance-server` is healthy or running.

- [ ] **Step 8: Smoke test formal lineage through the containerized API**

Run:

```powershell
$body = @'
{
  "producer": {
    "serviceName": "docker-smoke",
    "instanceId": "local-compose",
    "snapshotId": "docker-lineage-001"
  },
  "snapshotType": "FULL",
  "metadataList": [
    {
      "assetCode": "dwd_cell_profile",
      "assetName": "DWD Cell Profile",
      "metadataType": "TABLE",
      "sourceType": "HIVE",
      "domain": "wireless-rno",
      "owner": "network-team",
      "queryable": true,
      "federatedQueryable": true,
      "schema": [
        {"fieldName": "cell_id", "fieldType": "varchar", "ordinal": 1},
        {"fieldName": "rsrp_avg", "fieldType": "double", "ordinal": 2}
      ],
      "binding": {
        "sourceType": "HIVE",
        "catalog": "hive_catalog",
        "database": "dwd",
        "table": "dwd_cell_profile"
      }
    },
    {
      "assetCode": "ads_cell_profile",
      "assetName": "ADS Cell Profile",
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
        "table": "ads_cell_profile",
        "queryAdapter": "starrocks"
      },
      "lineage": {
        "upstreams": [
          {
            "assetCode": "dwd_cell_profile",
            "lineageType": "FIELD",
            "transformType": "SQL",
            "expression": "job:rno-profile-etl",
            "fieldMappings": [
              {
                "sourceField": "rsrp_avg",
                "targetField": "coverage_score",
                "expression": "case when rsrp_avg >= -95 then 100 else 60 end"
              }
            ]
          }
        ]
      }
    }
  ]
}
'@

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8080/rest/oss/inner/modelengineservice/v1/metadata/register `
  -ContentType "application/json" `
  -Body $body

$target = Invoke-RestMethod "http://localhost:8080/rest/oss/inner/modelengineservice/v1/metadata?assetCode=ads_cell_profile"
$lineage = Invoke-RestMethod "http://localhost:8080/rest/oss/inner/modelengineservice/v1/metadata/$($target.items[0].metadataId)/lineage?direction=up&depth=5"
$lineage.metadataId
$lineage.edges[0].lineageType
$lineage.fieldEdges[0].targetField
```

Expected: the final three printed values are the `ads_cell_profile` metadata ID, `FIELD`, and `coverage_score`.

- [ ] **Step 9: Commit Docker runtime changes**

Run:

```powershell
git add data-gov-platform/data-gov-server/pom.xml `
        data-gov-platform/data-gov-server/src/main/resources/application-docker.yml `
        data-gov-platform/data-gov-server/Dockerfile `
        app-compose.yml
git commit -m "Add Docker runtime for governance server"
```

## Task 6: Full Verification And Push Prep

**Files:**
- Verify all touched files.
- Verify Docker Compose changes render correctly.

- [ ] **Step 1: Run the full Maven test suite**

Run:

```powershell
cd data-gov-platform
mvn test
```

Expected: `BUILD SUCCESS`.

- [ ] **Step 2: Check whitespace and Compose configuration**

Run:

```powershell
git diff --check
docker compose -f ../shared-data-infra/compose.yaml --profile data-gov config
docker compose -f app-compose.yml config
docker compose -f app-compose.yml --profile governance config
```

Expected: `git diff --check` prints no issues. All three Compose config commands complete successfully.

- [ ] **Step 3: Inspect all work**

Run:

```powershell
git status -sb
git log --oneline origin/master..HEAD
```

Expected: branch is `master`, local commits are ahead of `origin/master` until pushed, and the last commits are the formal lineage and Docker runtime commits from this plan.

## Self-Review

- Spec coverage: Formal metadata lineage read path is covered by Task 4. Snapshot lineage ingestion is covered by Task 3. Contract additions for formal lineage declarations and response shape are covered by Task 1.
- Docker runtime coverage: Task 5 adds the Spring Boot container, explicit Docker profile, shared-infra config validation, health verification, and a formal lineage API smoke test through `localhost:8080`.
- Type consistency: `metadataId` maps to `data_asset.asset_id`. Formal response node and edge metadata IDs use existing asset IDs.
- Backward compatibility: Existing legacy `/api/lineage` routes still use `LineageDtos` and run in Tasks 2 through 6.
- Infrastructure: The plan reuses `../shared-data-infra` and does not duplicate Neo4j, HDFS, YARN, Hive, Kafka, StarRocks, Spark, Prometheus, or Grafana services in this repository. Compose validation commands from `AGENTS.md` are included in Tasks 5 and 6.
