package io.datagov.common.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.List;
import java.util.Map;

public final class QueryDtos {
    private QueryDtos() {
    }

    public record AssetQueryRequest(
            List<String> select,
            @Valid List<QueryFilter> filters,
            Integer limit,
            String subscriptionId,
            String consumerName,
            String environment
    ) {
    }

    public record QueryFilter(
            @NotBlank String field,
            @NotBlank String op,
            @NotNull Object value
    ) {
    }

    public record SqlQueryRequest(
            @NotBlank String sql,
            Integer limit,
            String subscriptionId,
            String consumerName,
            String environment
    ) {
    }

    public record QueryResponse(
            String queryId,
            List<String> columns,
            List<Map<String, Object>> rows,
            int rowCount,
            long elapsedMs
    ) {
    }
}
