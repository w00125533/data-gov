package io.datagov.server.query;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.dto.QueryDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.QueryRequestType;
import io.datagov.common.enums.QueryStatus;
import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.asset.AssetRepository;
import io.datagov.server.subscription.SubscriptionRepository;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Service
public class ProductQueryService {
    private static final Set<String> FILTER_OPS = Set.of("=", "!=", ">", ">=", "<", "<=", "LIKE", "IN");

    private final AssetRepository assetRepository;
    private final SubscriptionRepository subscriptionRepository;
    private final QueryRecordRepository queryRecordRepository;
    private final StarRocksQueryExecutor executor;
    private final StarRocksQueryProperties properties;
    private final StarRocksNameResolver nameResolver;

    public ProductQueryService(
            AssetRepository assetRepository,
            SubscriptionRepository subscriptionRepository,
            QueryRecordRepository queryRecordRepository,
            StarRocksQueryExecutor executor,
            StarRocksQueryProperties properties,
            StarRocksNameResolver nameResolver
    ) {
        this.assetRepository = assetRepository;
        this.subscriptionRepository = subscriptionRepository;
        this.queryRecordRepository = queryRecordRepository;
        this.executor = executor;
        this.properties = properties;
        this.nameResolver = nameResolver;
    }

    public QueryDtos.QueryResponse query(String assetCode, QueryDtos.AssetQueryRequest request) {
        AssetDtos.AssetResponse asset = assetRepository.findAssetByCode(assetCode)
                .orElseThrow(() -> new AssetNotFoundException(assetCode));
        String queryId = newId();
        Instant startedAt = Instant.now();
        List<String> selectedFields = List.of();
        List<QueryDtos.QueryFilter> filters = request == null || request.filters() == null
                ? List.of()
                : request.filters();
        String rewrittenSql = null;
        GovernanceDtos.SubscriptionResponse subscription = null;
        try {
            validateQueryable(asset);
            AssetDtos.PhysicalBindingResponse binding = assetRepository.findActiveBinding(asset.assetId())
                    .orElse(null);
            Map<String, AssetDtos.FieldResponse> fields = fieldsByName(asset.assetId());
            selectedFields = selectedFields(request, fields);
            List<Object> params = new ArrayList<>();
            String whereClause = buildWhere(filters, fields, params);
            int limit = clampLimit(request == null ? null : request.limit());
            rewrittenSql = "select " + selectedFields.stream().map(nameResolver::quote).reduce((a, b) -> a + ", " + b)
                    .orElse("*")
                    + " from " + nameResolver.tableName(binding)
                    + whereClause
                    + " limit " + limit;
            subscription = validateSubscription(request == null ? null : request.subscriptionId(), List.of(asset.assetId()));

            QueryResult result = executor.execute(
                    rewrittenSql,
                    params,
                    limit,
                    Duration.ofSeconds(properties.getQueryTimeoutSeconds()));
            long elapsedMs = Math.max(0, java.time.Duration.between(startedAt, Instant.now()).toMillis());
            insertRecord(queryId, asset, subscription, List.of(asset.assetCode()), selectedFields, filters, null,
                    rewrittenSql, QueryStatus.SUCCESS, null, null, result.rows().size(), elapsedMs, startedAt);
            updateSubscriptionRuntime(subscription);
            return new QueryDtos.QueryResponse(queryId, result.columns(), result.rows(), result.rows().size(), elapsedMs);
        } catch (QueryValidationException | QueryExecutionException ex) {
            long elapsedMs = Math.max(0, java.time.Duration.between(startedAt, Instant.now()).toMillis());
            insertRecord(queryId, asset, subscription, List.of(asset.assetCode()), selectedFields, filters, null,
                    rewrittenSql, QueryStatus.FAILED, ex instanceof QueryValidationException validation
                            ? validation.getErrorCode()
                            : ((QueryExecutionException) ex).getErrorCode(),
                    ex.getMessage(), null, elapsedMs, startedAt);
            updateSubscriptionRuntime(subscription);
            throw ex;
        }
    }

    private void validateQueryable(AssetDtos.AssetResponse asset) {
        if (asset.engine() == AssetEngine.KAFKA) {
            throw new QueryValidationException("KAFKA_QUERY_NOT_SUPPORTED", "Kafka assets are not queryable");
        }
        if (!asset.queryable()) {
            throw new QueryValidationException("ASSET_NOT_QUERYABLE", "Asset is not queryable");
        }
    }

    private Map<String, AssetDtos.FieldResponse> fieldsByName(String assetId) {
        Map<String, AssetDtos.FieldResponse> fields = new LinkedHashMap<>();
        for (AssetDtos.FieldResponse field : assetRepository.findFields(assetId)) {
            fields.put(field.fieldName(), field);
        }
        return fields;
    }

    private List<String> selectedFields(
            QueryDtos.AssetQueryRequest request,
            Map<String, AssetDtos.FieldResponse> fields
    ) {
        if (request == null || request.select() == null || request.select().isEmpty()) {
            return List.copyOf(fields.keySet());
        }
        for (String field : request.select()) {
            if (!fields.containsKey(field)) {
                throw new QueryValidationException("UNKNOWN_FIELD", "Unknown selected field: " + field);
            }
        }
        return List.copyOf(request.select());
    }

    private String buildWhere(
            List<QueryDtos.QueryFilter> filters,
            Map<String, AssetDtos.FieldResponse> fields,
            List<Object> params
    ) {
        if (filters.isEmpty()) {
            return "";
        }
        List<String> clauses = new ArrayList<>();
        for (QueryDtos.QueryFilter filter : filters) {
            if (!fields.containsKey(filter.field())) {
                throw new QueryValidationException("UNKNOWN_FIELD", "Unknown filter field: " + filter.field());
            }
            String op = filter.op().toUpperCase(Locale.ROOT);
            if (!FILTER_OPS.contains(op)) {
                throw new QueryValidationException("INVALID_FILTER", "Unsupported filter operator: " + filter.op());
            }
            if ("IN".equals(op)) {
                if (!(filter.value() instanceof List<?> values) || values.isEmpty()) {
                    throw new QueryValidationException("INVALID_FILTER", "IN filter requires a non-empty list value");
                }
                params.addAll(values);
                clauses.add(nameResolver.quote(filter.field()) + " in ("
                        + String.join(", ", java.util.Collections.nCopies(values.size(), "?")) + ")");
            } else {
                params.add(filter.value());
                clauses.add(nameResolver.quote(filter.field()) + " " + op + " ?");
            }
        }
        return " where " + String.join(" and ", clauses);
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

    private int clampLimit(Integer requestedLimit) {
        if (requestedLimit == null || requestedLimit <= 0) {
            return properties.getDefaultLimit();
        }
        return Math.min(requestedLimit, properties.getMaxLimit());
    }

    private void insertRecord(
            String queryId,
            AssetDtos.AssetResponse asset,
            GovernanceDtos.SubscriptionResponse subscription,
            List<String> referencedAssetCodes,
            List<String> selectedFields,
            List<QueryDtos.QueryFilter> filters,
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
                QueryRequestType.PRODUCT_API,
                asset.assetId(),
                subscription == null ? null : subscription.subscriptionId(),
                subscription == null ? null : subscription.consumerId(),
                referencedAssetCodes,
                selectedFields,
                filters,
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
