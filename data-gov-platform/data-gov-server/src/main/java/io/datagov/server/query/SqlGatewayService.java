package io.datagov.server.query;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.dto.QueryDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.QueryRequestType;
import io.datagov.common.enums.QueryStatus;
import io.datagov.server.asset.AssetRepository;
import io.datagov.server.subscription.SubscriptionRepository;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class SqlGatewayService {
    private final AssetRepository assetRepository;
    private final SubscriptionRepository subscriptionRepository;
    private final QueryRecordRepository queryRecordRepository;
    private final StarRocksQueryExecutor executor;
    private final StarRocksQueryProperties properties;
    private final StarRocksNameResolver nameResolver;
    private final SqlGuard sqlGuard;

    public SqlGatewayService(
            AssetRepository assetRepository,
            SubscriptionRepository subscriptionRepository,
            QueryRecordRepository queryRecordRepository,
            StarRocksQueryExecutor executor,
            StarRocksQueryProperties properties,
            StarRocksNameResolver nameResolver,
            SqlGuard sqlGuard
    ) {
        this.assetRepository = assetRepository;
        this.subscriptionRepository = subscriptionRepository;
        this.queryRecordRepository = queryRecordRepository;
        this.executor = executor;
        this.properties = properties;
        this.nameResolver = nameResolver;
        this.sqlGuard = sqlGuard;
    }

    public QueryDtos.QueryResponse query(QueryDtos.SqlQueryRequest request) {
        String queryId = newId();
        Instant startedAt = Instant.now();
        String sql = request == null ? null : request.sql();
        List<String> assetCodes = List.of();
        List<AssetDtos.AssetResponse> assets = List.of();
        String rewrittenSql = null;
        GovernanceDtos.SubscriptionResponse subscription = null;
        try {
            sql = sqlGuard.validateReadOnly(sql);
            assetCodes = sqlGuard.extractAssetCodes(sql);
            assets = resolveAssets(assetCodes);
            Map<String, String> physicalNames = new LinkedHashMap<>();
            for (AssetDtos.AssetResponse asset : assets) {
                AssetDtos.PhysicalBindingResponse binding = assetRepository.findActiveBinding(asset.assetId())
                        .orElse(null);
                physicalNames.put(asset.assetCode(), nameResolver.tableName(binding));
            }
            rewrittenSql = sqlGuard.rewriteSources(sql, physicalNames);
            int maxRows = properties.getMaxLimit();
            if (request.limit() != null && request.limit() > 0) {
                int limit = Math.min(request.limit(), properties.getMaxLimit());
                rewrittenSql = sqlGuard.forceLimit(rewrittenSql, limit, properties.getMaxLimit());
                maxRows = limit;
            } else {
                rewrittenSql = sqlGuard.appendLimitIfMissing(rewrittenSql, properties.getMaxLimit());
            }
            subscription = validateSubscription(request.subscriptionId(), assets.stream()
                    .map(AssetDtos.AssetResponse::assetId)
                    .toList());

            QueryResult result = executor.execute(
                    rewrittenSql,
                    List.of(),
                    maxRows,
                    Duration.ofSeconds(properties.getQueryTimeoutSeconds()));
            long elapsedMs = Math.max(0, Duration.between(startedAt, Instant.now()).toMillis());
            insertRecord(queryId, null, subscription, assetCodes, sql, rewrittenSql, QueryStatus.SUCCESS, null, null,
                    result.rows().size(), elapsedMs, startedAt);
            updateSubscriptionRuntime(subscription);
            return new QueryDtos.QueryResponse(queryId, result.columns(), result.rows(), result.rows().size(), elapsedMs);
        } catch (QueryValidationException | QueryExecutionException ex) {
            long elapsedMs = Math.max(0, Duration.between(startedAt, Instant.now()).toMillis());
            if (assetCodes.isEmpty()) {
                assetCodes = safeExtractAssetCodes(sql);
            }
            if (!assetCodes.isEmpty()) {
                insertRecord(queryId, firstAssetIdOrNull(assets), subscription, assetCodes, sql, rewrittenSql,
                        QueryStatus.FAILED,
                        ex instanceof QueryValidationException validation
                                ? validation.getErrorCode()
                                : ((QueryExecutionException) ex).getErrorCode(),
                        ex.getMessage(), null, elapsedMs, startedAt);
            }
            updateSubscriptionRuntime(subscription);
            throw ex;
        }
    }

    private List<AssetDtos.AssetResponse> resolveAssets(List<String> assetCodes) {
        boolean requiresFederated = assetCodes.size() > 1;
        return assetCodes.stream()
                .map(assetCode -> {
                    AssetDtos.AssetResponse asset = assetRepository.findAssetByCode(assetCode)
                            .orElseThrow(() -> new QueryValidationException(
                                    "UNKNOWN_SQL_ASSET",
                                    "Unknown SQL asset: " + assetCode));
                    if (asset.engine() == AssetEngine.KAFKA) {
                        throw new QueryValidationException("KAFKA_QUERY_NOT_SUPPORTED", "Kafka assets are not queryable");
                    }
                    if (requiresFederated && !asset.federatedQueryable()) {
                        throw new QueryValidationException(
                                "ASSET_NOT_QUERYABLE",
                                "Asset is not enabled for federated query");
                    }
                    if (!asset.queryable() && !asset.federatedQueryable()) {
                        throw new QueryValidationException("ASSET_NOT_QUERYABLE", "Asset is not queryable");
                    }
                    return asset;
                })
                .toList();
    }

    private List<String> safeExtractAssetCodes(String sql) {
        try {
            return sqlGuard.extractAssetCodes(sql == null ? "" : sql);
        } catch (QueryValidationException ex) {
            return List.of();
        }
    }

    private GovernanceDtos.SubscriptionResponse validateSubscription(String subscriptionId, List<String> assetIds) {
        if (subscriptionId == null || subscriptionId.isBlank()) {
            return null;
        }
        GovernanceDtos.SubscriptionResponse subscription = subscriptionRepository.findSubscription(subscriptionId)
                .orElseThrow(() -> new QueryValidationException("INVALID_SUBSCRIPTION", "Subscription not found"));
        if (!assetIds.contains(subscription.assetId())) {
            throw new QueryValidationException("INVALID_SUBSCRIPTION", "Subscription does not belong to queried asset");
        }
        return subscription;
    }

    private void updateSubscriptionRuntime(GovernanceDtos.SubscriptionResponse subscription) {
        if (subscription != null) {
            subscriptionRepository.updateLastRuntimeSeenAt(subscription.subscriptionId(), Instant.now());
        }
    }

    private String firstAssetIdOrNull(List<AssetDtos.AssetResponse> assets) {
        return assets.isEmpty() ? null : assets.get(0).assetId();
    }

    private void insertRecord(
            String queryId,
            String assetId,
            GovernanceDtos.SubscriptionResponse subscription,
            List<String> assetCodes,
            String sqlText,
            String rewrittenSql,
            QueryStatus status,
            String errorCode,
            String errorMessage,
            Integer rowCount,
            Long elapsedMs,
            Instant createdAt
    ) {
        queryRecordRepository.insert(new QueryRecord(
                queryId,
                QueryRequestType.SQL_GATEWAY,
                assetId,
                subscription == null ? null : subscription.subscriptionId(),
                subscription == null ? null : subscription.consumerId(),
                assetCodes,
                null,
                null,
                sqlText,
                rewrittenSql,
                status,
                errorCode,
                errorMessage,
                rowCount,
                elapsedMs,
                createdAt));
    }

    private String newId() {
        return "qry_" + UUID.randomUUID().toString().replace("-", "");
    }
}
