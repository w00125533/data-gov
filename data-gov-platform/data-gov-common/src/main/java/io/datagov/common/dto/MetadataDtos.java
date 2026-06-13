package io.datagov.common.dto;

import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LineageTransformType;
import io.datagov.common.enums.LineageType;
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
