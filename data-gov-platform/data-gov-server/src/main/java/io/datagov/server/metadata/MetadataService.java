package io.datagov.server.metadata;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.ObjectWriter;
import com.fasterxml.jackson.databind.SerializationFeature;
import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.MetadataDtos;
import io.datagov.common.enums.LifecycleStatus;
import io.datagov.common.enums.MetadataSyncItemStatus;
import io.datagov.common.enums.MetadataSyncMode;
import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.asset.AssetRepository;
import io.datagov.server.asset.AssetService;
import io.datagov.server.lineage.LineageService;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

@Service
public class MetadataService {
    private final AssetRepository assetRepository;
    private final AssetService assetService;
    private final LineageService lineageService;
    private final TransactionTemplate transactionTemplate;
    private final ObjectWriter declarationHashWriter;

    public MetadataService(
            AssetRepository assetRepository,
            AssetService assetService,
            LineageService lineageService,
            TransactionTemplate transactionTemplate,
            ObjectMapper objectMapper
    ) {
        this.assetRepository = assetRepository;
        this.assetService = assetService;
        this.lineageService = lineageService;
        this.transactionTemplate = transactionTemplate;
        this.declarationHashWriter = objectMapper.writer()
                .with(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS);
    }

    public MetadataDtos.MetadataSyncResponse registerSnapshot(
            MetadataDtos.MetadataSnapshotRegisterRequest request
    ) {
        try {
            return transactionTemplate.execute(status -> registerSnapshotInTransaction(request));
        } catch (DataAccessException ex) {
            throw new MetadataDataAccessException("Failed to register metadata snapshot", ex);
        }
    }

    private MetadataDtos.MetadataSyncResponse registerSnapshotInTransaction(
            MetadataDtos.MetadataSnapshotRegisterRequest request
    ) {
        MetadataSyncMode syncMode = request.syncMode() == null ? MetadataSyncMode.FULL : request.syncMode();
        if (syncMode != MetadataSyncMode.FULL) {
            throw new IllegalArgumentException("Unsupported metadata syncMode: " + syncMode);
        }

        Instant syncedAt = Instant.now();
        List<MetadataDtos.MetadataSyncItemResponse> items = new ArrayList<>();
        Set<String> currentAssetCodes = new LinkedHashSet<>();
        Map<String, AssetDtos.AssetResponse> assetsByCode = new LinkedHashMap<>();
        int created = 0;
        int updated = 0;
        int unchanged = 0;

        for (MetadataDtos.MetadataItemRequest item : request.metadataList()) {
            currentAssetCodes.add(item.assetCode());
            String declarationHash = declarationHash(item);
            AssetDtos.AssetResponse existing = assetRepository.findAssetByCode(item.assetCode()).orElse(null);
            AssetDtos.AssetResponse asset;
            MetadataSyncItemStatus itemStatus;

            if (existing == null) {
                asset = assetService.register(toRegisterRequest(item)).asset();
                itemStatus = MetadataSyncItemStatus.CREATED;
                created++;
            } else if (Objects.equals(assetRepository.findDeclarationHash(existing.assetId()), declarationHash)) {
                asset = existing;
                itemStatus = MetadataSyncItemStatus.UNCHANGED;
                unchanged++;
            } else {
                asset = assetService.register(toRegisterRequest(item)).asset();
                itemStatus = MetadataSyncItemStatus.UPDATED;
                updated++;
            }

            assetRepository.updateSnapshotScope(
                    asset.assetId(),
                    request.producer().serviceName(),
                    request.producer().serviceType(),
                    request.producer().environment(),
                    request.producer().owner(),
                    declarationHash,
                    request.producer().instanceId(),
                    syncedAt);
            assetsByCode.put(asset.assetCode(), asset);
            items.add(new MetadataDtos.MetadataSyncItemResponse(
                    asset.assetId(),
                    asset.assetCode(),
                    itemStatus));
        }

        Map<String, AssetDtos.AssetResponse> lineageScopeAssetsByCode = lineageScopeAssetsByCode(
                request.producer(),
                assetsByCode);
        lineageService.replaceSnapshotLineage(
                request.producer(),
                request.metadataList(),
                assetsByCode,
                lineageScopeAssetsByCode);
        int removed = markMissingScopedAssetsRemoved(request, currentAssetCodes, syncedAt, items);

        return new MetadataDtos.MetadataSyncResponse(
                new MetadataDtos.MetadataSyncScope(
                        request.producer().serviceName(),
                        request.producer().environment()),
                created,
                updated,
                unchanged,
                removed,
                List.copyOf(items),
                syncedAt);
    }

    private Map<String, AssetDtos.AssetResponse> lineageScopeAssetsByCode(
            MetadataDtos.ProducerRequest producer,
            Map<String, AssetDtos.AssetResponse> currentAssetsByCode
    ) {
        Map<String, AssetDtos.AssetResponse> scopeAssetsByCode = new LinkedHashMap<>();
        for (AssetDtos.AssetResponse scopedAsset : assetRepository.findAssetsInProducerScope(
                producer.serviceName(),
                producer.environment())) {
            scopeAssetsByCode.put(scopedAsset.assetCode(), scopedAsset);
        }
        scopeAssetsByCode.putAll(currentAssetsByCode);
        return scopeAssetsByCode;
    }

    private int markMissingScopedAssetsRemoved(
            MetadataDtos.MetadataSnapshotRegisterRequest request,
            Set<String> currentAssetCodes,
            Instant syncedAt,
            List<MetadataDtos.MetadataSyncItemResponse> items
    ) {
        int removed = 0;
        for (AssetDtos.AssetResponse scopedAsset : assetRepository.findAssetsInProducerScope(
                request.producer().serviceName(),
                request.producer().environment())) {
            if (currentAssetCodes.contains(scopedAsset.assetCode())
                    || scopedAsset.lifecycleStatus() != LifecycleStatus.ACTIVE) {
                continue;
            }
            assetRepository.markRemovedBySnapshot(scopedAsset.assetId(), syncedAt);
            items.add(new MetadataDtos.MetadataSyncItemResponse(
                    scopedAsset.assetId(),
                    scopedAsset.assetCode(),
                    MetadataSyncItemStatus.REMOVED_BY_SNAPSHOT));
            removed++;
        }
        return removed;
    }

    public MetadataDtos.MetadataListResponse listMetadata(
            String keyword,
            String domain,
            String metadataType,
            String owner,
            int page,
            int size
    ) {
        try {
            int cappedPage = Math.max(1, page);
            int cappedSize = Math.min(100, Math.max(1, size));
            List<MetadataDtos.MetadataSummaryResponse> filtered = assetRepository.listAssets().stream()
                    .filter(asset -> matchesKeyword(asset, keyword))
                    .filter(asset -> isBlank(domain) || domain.equals(asset.domain()))
                    .filter(asset -> isBlank(metadataType)
                            || metadataType.equalsIgnoreCase(asset.assetType().name()))
                    .filter(asset -> isBlank(owner) || owner.equals(asset.owner()))
                    .map(this::toSummaryResponse)
                    .toList();

            long offset = ((long) cappedPage - 1L) * cappedSize;
            int fromIndex = offset >= filtered.size() ? filtered.size() : (int) offset;
            int toIndex = (int) Math.min((long) filtered.size(), offset + cappedSize);
            return new MetadataDtos.MetadataListResponse(
                    filtered.subList(fromIndex, toIndex),
                    cappedPage,
                    cappedSize,
                    filtered.size());
        } catch (DataAccessException ex) {
            throw new MetadataDataAccessException("Failed to list metadata", ex);
        }
    }

    public MetadataDtos.MetadataDetailResponse getMetadata(String metadataId) {
        try {
            AssetDtos.AssetResponse asset = assetRepository.findAssetById(metadataId)
                    .orElseThrow(() -> new AssetNotFoundException(metadataId));
            return toDetailResponse(
                    asset,
                    assetRepository.findFields(asset.assetId()),
                    assetRepository.findActiveBinding(asset.assetId()).orElse(null));
        } catch (DataAccessException ex) {
            throw new MetadataDataAccessException("Failed to read metadata: " + metadataId, ex);
        }
    }

    public MetadataDtos.MetadataMutationResponse updateMetadata(
            String metadataId,
            AssetDtos.UpdateAssetRequest request
    ) {
        try {
            AssetDtos.AssetResponse asset = assetRepository.findAssetById(metadataId)
                    .orElseThrow(() -> new AssetNotFoundException(metadataId));
            AssetDtos.AssetMutationResponse mutation = assetService.updateRuntime(asset.assetCode(), request);
            return new MetadataDtos.MetadataMutationResponse(
                    mutation.asset().asset().assetId(),
                    mutation.asset().asset().assetCode(),
                    "UPDATED",
                    mutation.asset().asset().updatedAt());
        } catch (DataAccessException ex) {
            throw new MetadataDataAccessException("Failed to update metadata: " + metadataId, ex);
        }
    }

    public MetadataDtos.MetadataMutationResponse unregisterMetadata(
            String metadataId,
            AssetDtos.UnregisterAssetRequest request
    ) {
        try {
            AssetDtos.AssetResponse asset = assetRepository.findAssetById(metadataId)
                    .orElseThrow(() -> new AssetNotFoundException(metadataId));
            AssetDtos.AssetMutationResponse mutation = assetService.unregisterRuntime(asset.assetCode(), request);
            return new MetadataDtos.MetadataMutationResponse(
                    mutation.asset().asset().assetId(),
                    mutation.asset().asset().assetCode(),
                    "UNREGISTERED",
                    mutation.asset().asset().updatedAt());
        } catch (DataAccessException ex) {
            throw new MetadataDataAccessException("Failed to unregister metadata: " + metadataId, ex);
        }
    }

    private MetadataDtos.MetadataSummaryResponse toSummaryResponse(AssetDtos.AssetResponse asset) {
        return new MetadataDtos.MetadataSummaryResponse(
                asset.assetId(),
                asset.assetCode(),
                asset.assetName(),
                asset.assetType(),
                asset.engine(),
                asset.domain(),
                asset.owner(),
                asset.queryable());
    }

    private MetadataDtos.MetadataDetailResponse toDetailResponse(
            AssetDtos.AssetResponse asset,
            List<AssetDtos.FieldResponse> fields,
            AssetDtos.PhysicalBindingResponse binding
    ) {
        return new MetadataDtos.MetadataDetailResponse(
                asset.assetId(),
                asset.assetCode(),
                asset.assetName(),
                asset.assetType(),
                asset.engine(),
                asset.domain(),
                asset.owner(),
                asset.description(),
                asset.queryable(),
                asset.federatedQueryable(),
                fields.stream().map(this::toFieldResponse).toList(),
                toBindingResponse(binding),
                asset.createdAt(),
                asset.updatedAt());
    }

    private MetadataDtos.MetadataFieldResponse toFieldResponse(AssetDtos.FieldResponse field) {
        return new MetadataDtos.MetadataFieldResponse(
                field.fieldName(),
                field.fieldType(),
                field.ordinalPosition(),
                field.nullable(),
                field.partitionKey(),
                field.primaryKey(),
                field.eventTime(),
                field.description(),
                field.expression());
    }

    private MetadataDtos.MetadataBindingResponse toBindingResponse(AssetDtos.PhysicalBindingResponse binding) {
        if (binding == null) {
            return null;
        }
        return new MetadataDtos.MetadataBindingResponse(
                binding.engine(),
                binding.catalogName(),
                binding.databaseName(),
                binding.schemaName(),
                binding.tableName(),
                binding.topicName(),
                qualifiedName(binding),
                binding.format(),
                binding.locationUri(),
                binding.connectionRef(),
                binding.queryAdapter(),
                binding.properties());
    }

    private AssetDtos.RegisterAssetRequest toRegisterRequest(MetadataDtos.MetadataItemRequest item) {
        return new AssetDtos.RegisterAssetRequest(
                item.assetCode(),
                item.assetName(),
                item.metadataType(),
                item.sourceType(),
                item.domain(),
                item.owner(),
                item.description(),
                LifecycleStatus.ACTIVE,
                item.queryable(),
                item.federatedQueryable(),
                item.schema() == null ? List.of() : item.schema().stream().map(this::toFieldRequest).toList(),
                toPhysicalBindingRequest(item.binding()));
    }

    private AssetDtos.FieldRequest toFieldRequest(MetadataDtos.MetadataFieldRequest field) {
        return new AssetDtos.FieldRequest(
                field.fieldName(),
                field.fieldType(),
                field.ordinal(),
                field.nullable(),
                field.partitionKey(),
                field.primaryKey(),
                field.eventTime(),
                field.description(),
                field.expression());
    }

    private AssetDtos.PhysicalBindingRequest toPhysicalBindingRequest(MetadataDtos.MetadataBindingRequest binding) {
        if (binding == null) {
            return null;
        }
        return new AssetDtos.PhysicalBindingRequest(
                binding.sourceType(),
                binding.catalog(),
                binding.database(),
                binding.schema(),
                binding.table(),
                binding.topic(),
                binding.format(),
                binding.locationUri(),
                binding.connectionRef(),
                binding.queryAdapter(),
                binding.properties());
    }

    private boolean matchesKeyword(AssetDtos.AssetResponse asset, String keyword) {
        if (isBlank(keyword)) {
            return true;
        }
        String normalized = keyword.toLowerCase(Locale.ROOT);
        return containsIgnoreCase(asset.assetId(), normalized)
                || containsIgnoreCase(asset.assetCode(), normalized)
                || containsIgnoreCase(asset.assetName(), normalized)
                || containsIgnoreCase(asset.description(), normalized);
    }

    private boolean containsIgnoreCase(String value, String normalizedKeyword) {
        return value != null && value.toLowerCase(Locale.ROOT).contains(normalizedKeyword);
    }

    private String qualifiedName(AssetDtos.PhysicalBindingResponse binding) {
        if (!isBlank(binding.topicName())) {
            return binding.topicName();
        }
        return joinNonBlank(
                binding.catalogName(),
                binding.databaseName(),
                binding.schemaName(),
                binding.tableName());
    }

    private String joinNonBlank(String... parts) {
        return Arrays.stream(parts)
                .filter(value -> !isBlank(value))
                .reduce((left, right) -> left + "." + right)
                .orElse(null);
    }

    private String declarationHash(MetadataDtos.MetadataItemRequest item) {
        try {
            byte[] itemJson = declarationHashWriter.writeValueAsBytes(item);
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return "sha256:" + HexFormat.of().formatHex(digest.digest(itemJson));
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("Failed to serialize metadata item for hashing: " + item.assetCode(), ex);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 digest is not available", ex);
        }
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
