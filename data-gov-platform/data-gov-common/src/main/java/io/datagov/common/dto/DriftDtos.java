package io.datagov.common.dto;

import io.datagov.common.enums.DriftStatus;
import io.datagov.common.enums.DriftType;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class DriftDtos {
    private DriftDtos() {
    }

    public record AnalyzeDriftRequest(
            Integer unusedAfterDays,
            Integer staleAfterDays,
            Integer usageLookbackDays
    ) {
    }

    public record DriftRecordResponse(
            String driftId,
            DriftType driftType,
            DriftStatus status,
            String assetId,
            String assetCode,
            String consumerId,
            String consumerName,
            String subscriptionId,
            Map<String, Object> evidence,
            Instant detectedAt,
            Instant resolvedAt
    ) {
    }

    public record DriftAnalysisResponse(
            int createdCount,
            int refreshedCount,
            List<DriftRecordResponse> records
    ) {
    }
}
