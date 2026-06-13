package io.datagov.server.lineage;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.dto.LineageDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LineageRelationType;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Map;

@Repository
public class LineageRepository {
    private static final TypeReference<Map<String, Object>> PROPERTIES_TYPE = new TypeReference<>() {
    };
    private static final TypeReference<List<String>> STRING_LIST_TYPE = new TypeReference<>() {
    };

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public LineageRepository(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public void insertEdge(LineageDtos.LineageEdgeResponse edge) {
        try {
            jdbcTemplate.update("""
                    insert into lineage_edge (
                        edge_id, source_asset_id, target_asset_id, relation_type, producer, process_name, job_name,
                        description, properties, active, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    edge.edgeId(), edge.source().assetId(), edge.target().assetId(), edge.relationType().name(),
                    edge.producer(), edge.processName(), edge.jobName(), edge.description(),
                    writeProperties(edge.properties()), edge.active(), Timestamp.from(edge.createdAt()),
                    Timestamp.from(edge.updatedAt()));
        } catch (DataAccessException ex) {
            throw new LineageDataAccessException("Failed to insert lineage edge", ex);
        }
    }

    public void deactivateProducerEdgesForAssets(List<String> assetIds, String producer, Instant now) {
        if (assetIds == null || assetIds.isEmpty()) {
            return;
        }

        try {
            String placeholders = placeholders(assetIds.size());
            Object[] args = new Object[(assetIds.size() * 2) + 2];
            int index = 0;
            args[index++] = Timestamp.from(now);
            args[index++] = producer;
            for (String assetId : assetIds) {
                args[index++] = assetId;
            }
            for (String assetId : assetIds) {
                args[index++] = assetId;
            }

            jdbcTemplate.update("""
                    update lineage_edge
                    set active = false, updated_at = ?
                    where active = true
                      and producer = ?
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
                        field_edge_id, lineage_edge_id, source_field_id, target_field_id, transform_expression,
                        description, properties, active, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    fieldEdge.fieldEdgeId(), fieldEdge.lineageEdgeId(), fieldEdge.sourceFieldId(),
                    fieldEdge.targetFieldId(), fieldEdge.transformExpression(), fieldEdge.description(),
                    writeProperties(fieldEdge.properties()), true, Timestamp.from(fieldEdge.createdAt()),
                    Timestamp.from(fieldEdge.updatedAt()));
        } catch (DataAccessException ex) {
            throw new LineageDataAccessException("Failed to insert lineage field edge", ex);
        }
    }

    public List<FieldLineageView> findActiveFieldEdgesForLineageIds(List<String> lineageEdgeIds) {
        if (lineageEdgeIds == null || lineageEdgeIds.isEmpty()) {
            return List.of();
        }

        try {
            String placeholders = placeholders(lineageEdgeIds.size());
            return jdbcTemplate.query("""
                    select lfe.field_edge_id, lfe.lineage_edge_id,
                           source_field.field_name as source_field,
                           target_field.field_name as target_field,
                           lfe.transform_expression
                    from lineage_field_edge lfe
                    left join asset_field source_field on source_field.field_id = lfe.source_field_id
                    left join asset_field target_field on target_field.field_id = lfe.target_field_id
                    where lfe.active = true and lfe.lineage_edge_id in (%s)
                    order by lfe.created_at, lfe.field_edge_id
                    """.formatted(placeholders), fieldLineageViewMapper(), lineageEdgeIds.toArray());
        } catch (DataAccessException ex) {
            throw new LineageDataAccessException("Failed to read lineage field edges", ex);
        }
    }

    public List<LineageDtos.LineageEdgeResponse> findActiveOutgoing(String assetId) {
        return findActiveEdges("""
                where le.active = true and le.source_asset_id = ?
                order by le.created_at, le.edge_id
                """, assetId);
    }

    public List<LineageDtos.LineageEdgeResponse> findActiveIncoming(String assetId) {
        return findActiveEdges("""
                where le.active = true and le.target_asset_id = ?
                order by le.created_at, le.edge_id
                """, assetId);
    }

    public List<LineageDtos.ImpactSubscription> findActiveSubscriptionsForAssetIds(List<String> assetIds) {
        if (assetIds == null || assetIds.isEmpty()) {
            return List.of();
        }

        try {
            String placeholders = placeholders(assetIds.size());
            return jdbcTemplate.query("""
                    select s.subscription_id, a.asset_code, s.consumer_id, c.consumer_name, s.usage_mode,
                           s.declared_fields, s.last_runtime_seen_at
                    from subscription s
                    join data_asset a on a.asset_id = s.asset_id
                    join consumer c on c.consumer_id = s.consumer_id
                    where s.status = 'ACTIVE' and s.asset_id in (%s)
                    order by a.asset_code, s.created_at, s.subscription_id
                    """.formatted(placeholders), impactSubscriptionMapper(), assetIds.toArray());
        } catch (DataAccessException ex) {
            throw new LineageDataAccessException("Failed to read impact subscriptions", ex);
        }
    }

    public List<LineageDtos.ImpactQueryUsage> findRecentQueriesForAssetCodes(
            List<String> assetIds,
            List<String> assetCodes,
            Instant since,
            int limit
    ) {
        if (assetIds == null || assetIds.isEmpty() || assetCodes == null || assetCodes.isEmpty()) {
            return List.of();
        }

        try {
            String assetIdPlaceholders = placeholders(assetIds.size());
            String referencedCodePredicates = String.join(" or ",
                    assetCodes.stream().map(ignored -> "referenced_asset_codes like ? escape '\\'").toList());
            Object[] args = new Object[assetIds.size() + assetCodes.size() + 2];
            int index = 0;
            args[index++] = Timestamp.from(since);
            for (String assetId : assetIds) {
                args[index++] = assetId;
            }
            for (String assetCode : assetCodes) {
                args[index++] = "%\"" + escapeLike(assetCode) + "\"%";
            }
            args[index] = limit;

            return jdbcTemplate.query("""
                    select query_id, request_type, status, referenced_asset_codes, created_at
                    from query_record
                    where created_at >= ?
                      and (asset_id in (%s) or (%s))
                    order by created_at desc, query_id desc
                    limit ?
                    """.formatted(assetIdPlaceholders, referencedCodePredicates),
                    impactQueryUsageMapper(),
                    args);
        } catch (DataAccessException ex) {
            throw new LineageDataAccessException("Failed to read impact query usage", ex);
        }
    }

    private List<LineageDtos.LineageEdgeResponse> findActiveEdges(String whereClause, String assetId) {
        try {
            return jdbcTemplate.query("""
                    select le.edge_id, le.relation_type, le.producer, le.process_name, le.job_name, le.description,
                           le.properties, le.active, le.created_at, le.updated_at,
                           src.asset_id as source_asset_id, src.asset_code as source_asset_code,
                           src.asset_name as source_asset_name, src.asset_type as source_asset_type,
                           src.engine as source_engine,
                           tgt.asset_id as target_asset_id, tgt.asset_code as target_asset_code,
                           tgt.asset_name as target_asset_name, tgt.asset_type as target_asset_type,
                           tgt.engine as target_engine
                    from lineage_edge le
                    join data_asset src on src.asset_id = le.source_asset_id
                    join data_asset tgt on tgt.asset_id = le.target_asset_id
                    """ + whereClause, edgeMapper(), assetId);
        } catch (DataAccessException ex) {
            throw new LineageDataAccessException("Failed to read lineage edges", ex);
        }
    }

    private RowMapper<LineageDtos.LineageEdgeResponse> edgeMapper() {
        return (rs, rowNum) -> new LineageDtos.LineageEdgeResponse(
                rs.getString("edge_id"),
                new LineageDtos.LineageAssetNode(
                        rs.getString("source_asset_id"),
                        rs.getString("source_asset_code"),
                        rs.getString("source_asset_name"),
                        AssetType.valueOf(rs.getString("source_asset_type")),
                        AssetEngine.valueOf(rs.getString("source_engine"))),
                new LineageDtos.LineageAssetNode(
                        rs.getString("target_asset_id"),
                        rs.getString("target_asset_code"),
                        rs.getString("target_asset_name"),
                        AssetType.valueOf(rs.getString("target_asset_type")),
                        AssetEngine.valueOf(rs.getString("target_engine"))),
                LineageRelationType.valueOf(rs.getString("relation_type")),
                rs.getString("producer"),
                rs.getString("process_name"),
                rs.getString("job_name"),
                rs.getString("description"),
                readProperties(rs.getString("properties")),
                rs.getBoolean("active"),
                rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at").toInstant());
    }

    private RowMapper<LineageDtos.ImpactSubscription> impactSubscriptionMapper() {
        return (rs, rowNum) -> new LineageDtos.ImpactSubscription(
                rs.getString("subscription_id"),
                rs.getString("asset_code"),
                rs.getString("consumer_id"),
                rs.getString("consumer_name"),
                rs.getString("usage_mode"),
                readStringList(rs.getString("declared_fields")),
                rs.getTimestamp("last_runtime_seen_at") == null
                        ? null
                        : rs.getTimestamp("last_runtime_seen_at").toInstant());
    }

    private RowMapper<LineageDtos.ImpactQueryUsage> impactQueryUsageMapper() {
        return (rs, rowNum) -> new LineageDtos.ImpactQueryUsage(
                rs.getString("query_id"),
                rs.getString("request_type"),
                rs.getString("status"),
                readStringList(rs.getString("referenced_asset_codes")),
                rs.getTimestamp("created_at").toInstant());
    }

    private RowMapper<FieldLineageView> fieldLineageViewMapper() {
        return (rs, rowNum) -> new FieldLineageView(
                rs.getString("field_edge_id"),
                rs.getString("lineage_edge_id"),
                rs.getString("source_field"),
                rs.getString("target_field"),
                rs.getString("transform_expression"));
    }

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

    private String writeProperties(Map<String, Object> properties) {
        if (properties == null || properties.isEmpty()) {
            return "{}";
        }
        try {
            return objectMapper.writeValueAsString(properties);
        } catch (Exception ex) {
            throw new LineageDataAccessException("Failed to serialize lineage properties", ex);
        }
    }

    private Map<String, Object> readProperties(String properties) {
        if (properties == null || properties.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(properties, PROPERTIES_TYPE);
        } catch (Exception ex) {
            throw new LineageDataAccessException("Failed to deserialize lineage properties", ex);
        }
    }

    private List<String> readStringList(String value) {
        if (value == null || value.isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(value, STRING_LIST_TYPE);
        } catch (Exception ex) {
            throw new LineageDataAccessException("Failed to deserialize lineage string list", ex);
        }
    }

    private String placeholders(int size) {
        return String.join(", ", java.util.Collections.nCopies(size, "?"));
    }

    private String escapeLike(String value) {
        return value
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_");
    }
}
