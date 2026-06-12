package io.datagov.server.asset;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.dto.AssetDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LifecycleStatus;
import io.datagov.common.enums.MetadataProducerType;
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
public class AssetRepository {
    private static final TypeReference<Map<String, Object>> PROPERTIES_TYPE = new TypeReference<>() {
    };

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public AssetRepository(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public Optional<AssetDtos.AssetResponse> findAssetByCode(String assetCode) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select asset_id, asset_code, asset_name, asset_type, engine, domain, owner, description,
                           lifecycle_status, schema_version, queryable, federated_queryable, created_at, updated_at
                    from data_asset
                    where asset_code = ?
                    """, assetMapper(), assetCode));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

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

    public List<AssetDtos.AssetResponse> listAssets() {
        return jdbcTemplate.query("""
                select asset_id, asset_code, asset_name, asset_type, engine, domain, owner, description,
                       lifecycle_status, schema_version, queryable, federated_queryable, created_at, updated_at
                from data_asset
                order by asset_code
                """, assetMapper());
    }

    public void insertAsset(AssetDtos.AssetResponse asset) {
        jdbcTemplate.update("""
                insert into data_asset (
                    asset_id, asset_code, asset_name, asset_type, engine, domain, owner, description,
                    lifecycle_status, schema_version, queryable, federated_queryable, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                asset.assetId(), asset.assetCode(), asset.assetName(), asset.assetType().name(), asset.engine().name(),
                asset.domain(), asset.owner(), asset.description(), asset.lifecycleStatus().name(), asset.schemaVersion(),
                asset.queryable(), asset.federatedQueryable(), Timestamp.from(asset.createdAt()),
                Timestamp.from(asset.updatedAt()));
    }

    public void updateAsset(AssetDtos.AssetResponse asset) {
        jdbcTemplate.update("""
                update data_asset
                set asset_name = ?, asset_type = ?, engine = ?, domain = ?, owner = ?, description = ?,
                    lifecycle_status = ?, schema_version = ?, queryable = ?, federated_queryable = ?, updated_at = ?
                where asset_id = ?
                """,
                asset.assetName(), asset.assetType().name(), asset.engine().name(), asset.domain(), asset.owner(),
                asset.description(), asset.lifecycleStatus().name(), asset.schemaVersion(), asset.queryable(),
                asset.federatedQueryable(), Timestamp.from(asset.updatedAt()), asset.assetId());
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

    public void replaceFields(String assetId, List<AssetDtos.FieldResponse> fields) {
        jdbcTemplate.update("delete from asset_field where asset_id = ?", assetId);
        for (AssetDtos.FieldResponse field : fields) {
            jdbcTemplate.update("""
                    insert into asset_field (
                        field_id, asset_id, field_name, field_type, ordinal_position, nullable, partition_key,
                        primary_key, event_time, description, expression, version, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    field.fieldId(), field.assetId(), field.fieldName(), field.fieldType(), field.ordinalPosition(),
                    field.nullable(), field.partitionKey(), field.primaryKey(), field.eventTime(), field.description(),
                    field.expression(), field.version(), Timestamp.from(Instant.now()), Timestamp.from(Instant.now()));
        }
    }

    public List<AssetDtos.FieldResponse> findFields(String assetId) {
        return jdbcTemplate.query("""
                select field_id, asset_id, field_name, field_type, ordinal_position, nullable, partition_key,
                       primary_key, event_time, description, expression, version
                from asset_field
                where asset_id = ?
                order by ordinal_position nulls last, field_name
                """, fieldMapper(), assetId);
    }

    public void replaceBinding(String assetId, AssetDtos.PhysicalBindingResponse binding) {
        jdbcTemplate.update("delete from asset_physical_binding where asset_id = ?", assetId);
        if (binding == null) {
            return;
        }
        jdbcTemplate.update("""
                insert into asset_physical_binding (
                    binding_id, asset_id, engine, catalog_name, database_name, schema_name, table_name, topic_name,
                    format, location_uri, connection_ref, query_adapter, properties, active, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                binding.bindingId(), binding.assetId(), binding.engine().name(), binding.catalogName(),
                binding.databaseName(), binding.schemaName(), binding.tableName(), binding.topicName(), binding.format(),
                binding.locationUri(), binding.connectionRef(), binding.queryAdapter(), writeProperties(binding.properties()),
                binding.active(), Timestamp.from(Instant.now()), Timestamp.from(Instant.now()));
    }

    public Optional<AssetDtos.PhysicalBindingResponse> findActiveBinding(String assetId) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select binding_id, asset_id, engine, catalog_name, database_name, schema_name, table_name,
                           topic_name, format, location_uri, connection_ref, query_adapter, properties, active
                    from asset_physical_binding
                    where asset_id = ? and active = true
                    """, bindingMapper(), assetId));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    private RowMapper<AssetDtos.AssetResponse> assetMapper() {
        return (rs, rowNum) -> new AssetDtos.AssetResponse(
                rs.getString("asset_id"),
                rs.getString("asset_code"),
                rs.getString("asset_name"),
                AssetType.valueOf(rs.getString("asset_type")),
                AssetEngine.valueOf(rs.getString("engine")),
                rs.getString("domain"),
                rs.getString("owner"),
                rs.getString("description"),
                LifecycleStatus.valueOf(rs.getString("lifecycle_status")),
                rs.getInt("schema_version"),
                rs.getBoolean("queryable"),
                rs.getBoolean("federated_queryable"),
                rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at").toInstant());
    }

    private RowMapper<AssetDtos.FieldResponse> fieldMapper() {
        return (rs, rowNum) -> new AssetDtos.FieldResponse(
                rs.getString("field_id"),
                rs.getString("asset_id"),
                rs.getString("field_name"),
                rs.getString("field_type"),
                (Integer) rs.getObject("ordinal_position"),
                rs.getBoolean("nullable"),
                rs.getBoolean("partition_key"),
                rs.getBoolean("primary_key"),
                rs.getBoolean("event_time"),
                rs.getString("description"),
                rs.getString("expression"),
                rs.getInt("version"));
    }

    private RowMapper<AssetDtos.PhysicalBindingResponse> bindingMapper() {
        return (rs, rowNum) -> new AssetDtos.PhysicalBindingResponse(
                rs.getString("binding_id"),
                rs.getString("asset_id"),
                AssetEngine.valueOf(rs.getString("engine")),
                rs.getString("catalog_name"),
                rs.getString("database_name"),
                rs.getString("schema_name"),
                rs.getString("table_name"),
                rs.getString("topic_name"),
                rs.getString("format"),
                rs.getString("location_uri"),
                rs.getString("connection_ref"),
                rs.getString("query_adapter"),
                readProperties(rs.getString("properties")),
                rs.getBoolean("active"));
    }

    private String writeProperties(Map<String, Object> properties) {
        if (properties == null || properties.isEmpty()) {
            return "{}";
        }
        try {
            return objectMapper.writeValueAsString(properties);
        } catch (Exception ex) {
            return "{}";
        }
    }

    private Map<String, Object> readProperties(String properties) {
        if (properties == null || properties.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(properties, PROPERTIES_TYPE);
        } catch (Exception ex) {
            return Map.of();
        }
    }
}
