package io.datagov.server.asset;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.LifecycleStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
public class AssetService {
    private final AssetRepository assetRepository;

    public AssetService(AssetRepository assetRepository) {
        this.assetRepository = assetRepository;
    }

    @Transactional
    public AssetDtos.AssetDetailResponse register(AssetDtos.RegisterAssetRequest request) {
        Instant now = Instant.now();
        AssetDtos.AssetResponse existing = assetRepository.findAssetByCode(request.assetCode()).orElse(null);
        boolean kafkaAsset = request.engine() == AssetEngine.KAFKA;
        boolean queryable = !kafkaAsset && Boolean.TRUE.equals(request.queryable());
        boolean federatedQueryable = !kafkaAsset && Boolean.TRUE.equals(request.federatedQueryable());

        AssetDtos.AssetResponse asset = new AssetDtos.AssetResponse(
                existing == null ? newId("asset_") : existing.assetId(),
                request.assetCode(),
                request.assetName(),
                request.assetType(),
                request.engine(),
                request.domain(),
                request.owner(),
                request.description(),
                request.lifecycleStatus() == null ? LifecycleStatus.DRAFT : request.lifecycleStatus(),
                existing == null ? 1 : existing.schemaVersion() + 1,
                queryable,
                federatedQueryable,
                existing == null ? now : existing.createdAt(),
                now);

        if (existing == null) {
            assetRepository.insertAsset(asset);
        } else {
            assetRepository.updateAsset(asset);
        }

        List<AssetDtos.FieldResponse> fields = toFieldResponses(asset.assetId(), request.fields());
        assetRepository.replaceFields(asset.assetId(), fields);
        AssetDtos.PhysicalBindingResponse binding = toBindingResponse(asset.assetId(), request.physicalBinding());
        assetRepository.replaceBinding(asset.assetId(), binding);
        return new AssetDtos.AssetDetailResponse(asset, fields, binding);
    }

    public List<AssetDtos.AssetResponse> listAssets() {
        return assetRepository.listAssets();
    }

    public AssetDtos.AssetDetailResponse getAsset(String assetCode) {
        AssetDtos.AssetResponse asset = requireAsset(assetCode);
        return new AssetDtos.AssetDetailResponse(
                asset,
                assetRepository.findFields(asset.assetId()),
                assetRepository.findActiveBinding(asset.assetId()).orElse(null));
    }

    public List<AssetDtos.FieldResponse> getSchema(String assetCode) {
        AssetDtos.AssetResponse asset = requireAsset(assetCode);
        return assetRepository.findFields(asset.assetId());
    }

    public AssetDtos.PhysicalBindingResponse getBinding(String assetCode) {
        AssetDtos.AssetResponse asset = requireAsset(assetCode);
        return assetRepository.findActiveBinding(asset.assetId())
                .orElseThrow(() -> new AssetNotFoundException(assetCode));
    }

    private AssetDtos.AssetResponse requireAsset(String assetCode) {
        return assetRepository.findAssetByCode(assetCode)
                .orElseThrow(() -> new AssetNotFoundException(assetCode));
    }

    private List<AssetDtos.FieldResponse> toFieldResponses(String assetId, List<AssetDtos.FieldRequest> fields) {
        if (fields == null) {
            return List.of();
        }
        return fields.stream()
                .map(field -> new AssetDtos.FieldResponse(
                        newId("field_"),
                        assetId,
                        field.fieldName(),
                        field.fieldType(),
                        field.ordinalPosition(),
                        field.nullable() == null || field.nullable(),
                        Boolean.TRUE.equals(field.partitionKey()),
                        Boolean.TRUE.equals(field.primaryKey()),
                        Boolean.TRUE.equals(field.eventTime()),
                        field.description(),
                        field.expression(),
                        1))
                .toList();
    }

    private AssetDtos.PhysicalBindingResponse toBindingResponse(
            String assetId,
            AssetDtos.PhysicalBindingRequest binding
    ) {
        if (binding == null) {
            return null;
        }
        return new AssetDtos.PhysicalBindingResponse(
                newId("bind_"),
                assetId,
                binding.engine(),
                binding.catalogName(),
                binding.databaseName(),
                binding.schemaName(),
                binding.tableName(),
                binding.topicName(),
                binding.format(),
                binding.locationUri(),
                binding.connectionRef(),
                binding.queryAdapter(),
                binding.properties() == null ? java.util.Map.of() : binding.properties(),
                true);
    }

    private String newId(String prefix) {
        return prefix + UUID.randomUUID().toString().replace("-", "");
    }
}
