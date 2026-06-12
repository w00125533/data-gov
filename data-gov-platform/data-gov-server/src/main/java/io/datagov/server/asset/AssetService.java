package io.datagov.server.asset;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.EventDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.LifecycleStatus;
import io.datagov.server.event.EventService;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.IntStream;

@Service
public class AssetService {
    private final AssetRepository assetRepository;
    private final TransactionTemplate transactionTemplate;
    private final EventService eventService;

    public AssetService(
            AssetRepository assetRepository,
            TransactionTemplate transactionTemplate,
            EventService eventService
    ) {
        this.assetRepository = assetRepository;
        this.transactionTemplate = transactionTemplate;
        this.eventService = eventService;
    }

    public AssetDtos.AssetDetailResponse register(AssetDtos.RegisterAssetRequest request) {
        try {
            return transactionTemplate.execute(status -> registerInTransaction(request, false));
        } catch (DuplicateKeyException ex) {
            return transactionTemplate.execute(status -> registerInTransaction(request, true));
        }
    }

    private AssetDtos.AssetDetailResponse registerInTransaction(
            AssetDtos.RegisterAssetRequest request,
            boolean forceExisting
    ) {
        Instant now = Instant.now();
        AssetDtos.AssetResponse existing = assetRepository.findAssetByCode(request.assetCode()).orElse(null);
        boolean kafkaAsset = request.engine() == AssetEngine.KAFKA;
        boolean queryable = !kafkaAsset && Boolean.TRUE.equals(request.queryable());
        boolean federatedQueryable = !kafkaAsset && Boolean.TRUE.equals(request.federatedQueryable());

        if (existing == null && forceExisting) {
            existing = assetRepository.findAssetByCode(request.assetCode())
                    .orElseThrow(() -> new IllegalStateException(
                            "Asset registration retry could not find duplicate asset code: " + request.assetCode()));
        }

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

    public AssetDtos.AssetMutationResponse updateRuntime(
            String assetCode,
            AssetDtos.UpdateAssetRequest request
    ) {
        AssetDtos.AssetDetailResponse detail =
                transactionTemplate.execute(status -> updateRuntimeInTransaction(assetCode, request));
        EventDtos.CreateAssetEventResponse event = eventService.createEvent(
                assetCode,
                new EventDtos.CreateAssetEventRequest(
                        request.eventType() == null ? AssetEventType.SCHEMA_CHANGE : request.eventType(),
                        request.severity(),
                        updatePayload(detail.asset(), request)));
        return new AssetDtos.AssetMutationResponse(detail, event);
    }

    private AssetDtos.AssetDetailResponse updateRuntimeInTransaction(
            String assetCode,
            AssetDtos.UpdateAssetRequest request
    ) {
        AssetDtos.AssetResponse existing = requireAsset(assetCode);
        AssetEngine engine = request.engine() == null ? existing.engine() : request.engine();
        boolean kafkaAsset = engine == AssetEngine.KAFKA;
        boolean queryable = !kafkaAsset && (
                request.queryable() == null ? existing.queryable() : Boolean.TRUE.equals(request.queryable()));
        boolean federatedQueryable = !kafkaAsset && (
                request.federatedQueryable() == null
                        ? existing.federatedQueryable()
                        : Boolean.TRUE.equals(request.federatedQueryable()));
        Instant now = Instant.now();

        AssetDtos.AssetResponse updated = new AssetDtos.AssetResponse(
                existing.assetId(),
                existing.assetCode(),
                request.assetName() == null ? existing.assetName() : request.assetName(),
                request.assetType() == null ? existing.assetType() : request.assetType(),
                engine,
                request.domain() == null ? existing.domain() : request.domain(),
                request.owner() == null ? existing.owner() : request.owner(),
                request.description() == null ? existing.description() : request.description(),
                request.lifecycleStatus() == null ? existing.lifecycleStatus() : request.lifecycleStatus(),
                existing.schemaVersion() + 1,
                queryable,
                federatedQueryable,
                existing.createdAt(),
                now);

        assetRepository.updateAsset(updated);
        if (request.fields() != null) {
            assetRepository.replaceFields(updated.assetId(), toFieldResponses(updated.assetId(), request.fields()));
        }
        if (request.physicalBinding() != null) {
            assetRepository.replaceBinding(
                    updated.assetId(),
                    toBindingResponse(updated.assetId(), request.physicalBinding()));
        }

        return new AssetDtos.AssetDetailResponse(
                updated,
                assetRepository.findFields(updated.assetId()),
                assetRepository.findActiveBinding(updated.assetId()).orElse(null));
    }

    public AssetDtos.AssetMutationResponse unregisterRuntime(
            String assetCode,
            AssetDtos.UnregisterAssetRequest request
    ) {
        AssetDtos.AssetDetailResponse detail =
                transactionTemplate.execute(status -> unregisterRuntimeInTransaction(assetCode));
        EventDtos.CreateAssetEventResponse event = eventService.createEvent(
                assetCode,
                new EventDtos.CreateAssetEventRequest(
                        AssetEventType.OFFLINE,
                        "WARN",
                        unregisterPayload(detail.asset(), request)));
        return new AssetDtos.AssetMutationResponse(detail, event);
    }

    private AssetDtos.AssetDetailResponse unregisterRuntimeInTransaction(String assetCode) {
        AssetDtos.AssetResponse existing = requireAsset(assetCode);
        Instant now = Instant.now();
        AssetDtos.AssetResponse offline = new AssetDtos.AssetResponse(
                existing.assetId(),
                existing.assetCode(),
                existing.assetName(),
                existing.assetType(),
                existing.engine(),
                existing.domain(),
                existing.owner(),
                existing.description(),
                LifecycleStatus.OFFLINE,
                existing.schemaVersion() + 1,
                false,
                false,
                existing.createdAt(),
                now);
        assetRepository.updateAsset(offline);
        return new AssetDtos.AssetDetailResponse(
                offline,
                assetRepository.findFields(offline.assetId()),
                assetRepository.findActiveBinding(offline.assetId()).orElse(null));
    }

    private Map<String, Object> updatePayload(
            AssetDtos.AssetResponse asset,
            AssetDtos.UpdateAssetRequest request
    ) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("operation", "PATCH_ASSET");
        payload.put("assetCode", asset.assetCode());
        payload.put("schemaVersion", asset.schemaVersion());
        payload.put("changedSections", changedSections(request));
        return Map.copyOf(payload);
    }

    private Map<String, Object> unregisterPayload(
            AssetDtos.AssetResponse asset,
            AssetDtos.UnregisterAssetRequest request
    ) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("operation", "DELETE_ASSET");
        payload.put("assetCode", asset.assetCode());
        payload.put("schemaVersion", asset.schemaVersion());
        payload.put("reason", request.reason());
        if (request.operator() != null && !request.operator().isBlank()) {
            payload.put("operator", request.operator());
        }
        return Map.copyOf(payload);
    }

    private List<String> changedSections(AssetDtos.UpdateAssetRequest request) {
        List<String> sections = new ArrayList<>();
        if (request.assetName() != null
                || request.assetType() != null
                || request.engine() != null
                || request.domain() != null
                || request.owner() != null
                || request.description() != null
                || request.lifecycleStatus() != null
                || request.queryable() != null
                || request.federatedQueryable() != null) {
            sections.add("asset");
        }
        if (request.fields() != null) {
            sections.add("fields");
        }
        if (request.physicalBinding() != null) {
            sections.add("binding");
        }
        if (sections.isEmpty()) {
            sections.add("asset");
        }
        return List.copyOf(sections);
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
        return IntStream.range(0, fields.size())
                .mapToObj(index -> {
                    AssetDtos.FieldRequest field = fields.get(index);
                    return new AssetDtos.FieldResponse(
                        newId("field_"),
                        assetId,
                        field.fieldName(),
                        field.fieldType(),
                        field.ordinalPosition() == null ? index + 1 : field.ordinalPosition(),
                        field.nullable() == null || field.nullable(),
                        Boolean.TRUE.equals(field.partitionKey()),
                        Boolean.TRUE.equals(field.primaryKey()),
                        Boolean.TRUE.equals(field.eventTime()),
                        field.description(),
                        field.expression(),
                        1);
                })
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
