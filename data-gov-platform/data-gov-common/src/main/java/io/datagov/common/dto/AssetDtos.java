package io.datagov.common.dto;

import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LifecycleStatus;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class AssetDtos {
    private AssetDtos() {
    }

    public record RegisterAssetRequest(
            @NotBlank String assetCode,
            String assetName,
            @NotNull AssetType assetType,
            @NotNull AssetEngine engine,
            String domain,
            String owner,
            String description,
            LifecycleStatus lifecycleStatus,
            Boolean queryable,
            Boolean federatedQueryable,
            @Valid List<FieldRequest> fields,
            @Valid PhysicalBindingRequest physicalBinding
    ) {
    }

    public record FieldRequest(
            @NotBlank String fieldName,
            @NotBlank String fieldType,
            Integer ordinalPosition,
            Boolean nullable,
            Boolean partitionKey,
            Boolean primaryKey,
            Boolean eventTime,
            String description,
            String expression
    ) {
    }

    public record PhysicalBindingRequest(
            @NotNull AssetEngine engine,
            String catalogName,
            String databaseName,
            String schemaName,
            String tableName,
            String topicName,
            String format,
            String locationUri,
            String connectionRef,
            String queryAdapter,
            Map<String, Object> properties
    ) {
    }

    public record AssetResponse(
            String assetId,
            String assetCode,
            String assetName,
            AssetType assetType,
            AssetEngine engine,
            String domain,
            String owner,
            String description,
            LifecycleStatus lifecycleStatus,
            int schemaVersion,
            boolean queryable,
            boolean federatedQueryable,
            Instant createdAt,
            Instant updatedAt
    ) {
    }

    public record FieldResponse(
            String fieldId,
            String assetId,
            String fieldName,
            String fieldType,
            Integer ordinalPosition,
            boolean nullable,
            boolean partitionKey,
            boolean primaryKey,
            boolean eventTime,
            String description,
            String expression,
            int version
    ) {
    }

    public record PhysicalBindingResponse(
            String bindingId,
            String assetId,
            AssetEngine engine,
            String catalogName,
            String databaseName,
            String schemaName,
            String tableName,
            String topicName,
            String format,
            String locationUri,
            String connectionRef,
            String queryAdapter,
            Map<String, Object> properties,
            boolean active
    ) {
    }

    public record AssetDetailResponse(
            AssetResponse asset,
            List<FieldResponse> fields,
            PhysicalBindingResponse binding
    ) {
    }
}
