package io.datagov.common.dto;

import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LineageDirection;
import io.datagov.common.enums.LineageRelationType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class LineageDtos {
    private LineageDtos() {
    }

    public record CreateLineageEdgeRequest(
            @NotBlank String sourceAssetCode,
            @NotBlank String targetAssetCode,
            @NotNull LineageRelationType relationType,
            String producer,
            String processName,
            String jobName,
            String description,
            Map<String, Object> properties
    ) {
    }

    public record LineageAssetNode(
            String assetId,
            String assetCode,
            String assetName,
            AssetType assetType,
            AssetEngine engine
    ) {
    }

    public record LineageEdgeResponse(
            String edgeId,
            LineageAssetNode source,
            LineageAssetNode target,
            LineageRelationType relationType,
            String producer,
            String processName,
            String jobName,
            String description,
            Map<String, Object> properties,
            boolean active,
            Instant createdAt,
            Instant updatedAt
    ) {
    }

    public record LineageGraphResponse(
            LineageAssetNode root,
            LineageDirection direction,
            int depth,
            List<LineageAssetNode> nodes,
            List<LineageEdgeResponse> edges
    ) {
    }

    public record ImpactSubscription(
            String subscriptionId,
            String assetCode,
            String consumerId,
            String consumerName,
            String usageMode,
            List<String> declaredFields,
            Instant lastRuntimeSeenAt
    ) {
    }

    public record ImpactQueryUsage(
            String queryId,
            String requestType,
            String status,
            List<String> referencedAssetCodes,
            Instant createdAt
    ) {
    }

    public record ImpactResponse(
            LineageAssetNode root,
            int depth,
            LineageGraphResponse downstreamLineage,
            List<ImpactSubscription> subscriptions,
            List<ImpactQueryUsage> recentQueries
    ) {
    }
}
