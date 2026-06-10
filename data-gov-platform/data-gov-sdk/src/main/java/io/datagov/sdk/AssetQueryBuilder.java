package io.datagov.sdk;

import io.datagov.common.dto.QueryDtos;

import java.time.temporal.TemporalAccessor;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Objects;
import java.util.stream.StreamSupport;

public final class AssetQueryBuilder {
    private final DefaultDataGovClient client;
    private final String assetCode;
    private final List<String> select;
    private final List<QueryDtos.QueryFilter> filters;
    private final Integer limit;
    private final String subscriptionId;
    private final String consumerName;
    private final String environment;

    AssetQueryBuilder(DefaultDataGovClient client, String assetCode) {
        this(client, assetCode, List.of(), List.of(), null, null, null, null);
    }

    private AssetQueryBuilder(
            DefaultDataGovClient client,
            String assetCode,
            List<String> select,
            List<QueryDtos.QueryFilter> filters,
            Integer limit,
            String subscriptionId,
            String consumerName,
            String environment
    ) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        this.assetCode = Objects.requireNonNull(assetCode, "assetCode must not be null");
        this.select = List.copyOf(select);
        this.filters = List.copyOf(filters);
        this.limit = limit;
        this.subscriptionId = subscriptionId;
        this.consumerName = consumerName;
        this.environment = environment;
    }

    public AssetQueryBuilder select(String... fields) {
        return copy(Arrays.asList(fields), filters, limit, subscriptionId, consumerName, environment);
    }

    public AssetQueryBuilder where(String field, String op, Object value) {
        List<QueryDtos.QueryFilter> nextFilters = new ArrayList<>(filters);
        nextFilters.add(new QueryDtos.QueryFilter(field, op, normalizeFilterValue(value)));
        return copy(select, nextFilters, limit, subscriptionId, consumerName, environment);
    }

    public AssetQueryBuilder limit(int limit) {
        return copy(select, filters, limit, subscriptionId, consumerName, environment);
    }

    public AssetQueryBuilder subscriptionId(String subscriptionId) {
        return copy(select, filters, limit, subscriptionId, consumerName, environment);
    }

    public AssetQueryBuilder consumerName(String consumerName) {
        return copy(select, filters, limit, subscriptionId, consumerName, environment);
    }

    public AssetQueryBuilder environment(String environment) {
        return copy(select, filters, limit, subscriptionId, consumerName, environment);
    }

    public QueryDtos.QueryResponse query() {
        QueryDtos.AssetQueryRequest request = new QueryDtos.AssetQueryRequest(
                select,
                filters,
                limit,
                subscriptionId,
                consumerName,
                environment
        );
        return client.queryAsset(assetCode, request);
    }

    private AssetQueryBuilder copy(
            List<String> select,
            List<QueryDtos.QueryFilter> filters,
            Integer limit,
            String subscriptionId,
            String consumerName,
            String environment
    ) {
        return new AssetQueryBuilder(client, assetCode, select, filters, limit, subscriptionId, consumerName, environment);
    }

    private static Object normalizeFilterValue(Object value) {
        if (value instanceof TemporalAccessor) {
            return value.toString();
        }
        if (value instanceof Iterable<?> iterable) {
            return StreamSupport.stream(iterable.spliterator(), false)
                    .map(AssetQueryBuilder::normalizeFilterValue)
                    .toList();
        }
        return value;
    }
}
