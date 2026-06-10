package io.datagov.server.query;

import io.datagov.common.enums.QueryRequestType;
import io.datagov.common.enums.QueryStatus;

import java.time.Instant;

public record QueryRecord(
        String queryId,
        QueryRequestType requestType,
        String assetId,
        String subscriptionId,
        String consumerId,
        Object referencedAssetCodes,
        Object selectedFields,
        Object filters,
        String sqlText,
        String rewrittenSql,
        QueryStatus status,
        String errorCode,
        String errorMessage,
        Integer rowCount,
        Long elapsedMs,
        Instant createdAt
) {
}
