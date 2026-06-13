package io.datagov.common.dto;

import io.datagov.common.enums.LineageDirection;
import io.datagov.common.enums.LineageType;

import java.util.List;

public final class FormalLineageDtos {
    private FormalLineageDtos() {
    }

    public record FormalLineageNode(
            String metadataId,
            String assetCode,
            String assetName
    ) {
    }

    public record FormalLineageEdge(
            String sourceMetadataId,
            String sourceAssetCode,
            String targetMetadataId,
            String targetAssetCode,
            LineageType lineageType,
            LineageDirection direction,
            String expression
    ) {
    }

    public record FormalFieldLineageEdge(
            String sourceMetadataId,
            String sourceAssetCode,
            String sourceField,
            String targetMetadataId,
            String targetAssetCode,
            String targetField,
            LineageType lineageType,
            LineageDirection direction,
            String expression
    ) {
    }

    public record FormalLineageResponse(
            String metadataId,
            LineageDirection direction,
            int depth,
            List<FormalLineageNode> nodes,
            List<FormalLineageEdge> edges,
            List<FormalFieldLineageEdge> fieldEdges
    ) {
    }
}
