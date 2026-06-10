package io.datagov.server.lineage;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.LineageDtos;
import io.datagov.common.enums.LineageDirection;
import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.asset.AssetRepository;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class LineageService {
    private final AssetRepository assetRepository;
    private final LineageRepository lineageRepository;

    public LineageService(AssetRepository assetRepository, LineageRepository lineageRepository) {
        this.assetRepository = assetRepository;
        this.lineageRepository = lineageRepository;
    }

    public LineageDtos.LineageEdgeResponse createEdge(LineageDtos.CreateLineageEdgeRequest request) {
        AssetDtos.AssetResponse source = requireAsset(request.sourceAssetCode());
        AssetDtos.AssetResponse target = requireAsset(request.targetAssetCode());
        if (source.assetId().equals(target.assetId())) {
            throw new LineageValidationException(
                    "INVALID_LINEAGE_EDGE",
                    "Lineage edge source and target must be different assets");
        }

        Instant now = Instant.now();
        LineageDtos.LineageEdgeResponse edge = new LineageDtos.LineageEdgeResponse(
                newId("lin_"),
                toNode(source),
                toNode(target),
                request.relationType(),
                request.producer(),
                request.processName(),
                request.jobName(),
                request.description(),
                request.properties() == null ? Map.of() : request.properties(),
                true,
                now,
                now);
        lineageRepository.insertEdge(edge);
        return edge;
    }

    public LineageDtos.LineageGraphResponse getLineage(String assetCode, String direction, int depth) {
        return getLineage(assetCode, parseDirection(direction), depth);
    }

    public LineageDtos.LineageGraphResponse getLineage(String assetCode, LineageDirection direction, int depth) {
        LineageDtos.LineageAssetNode root = toNode(requireAsset(assetCode));
        int boundedDepth = clampDepth(depth);
        Map<String, LineageDtos.LineageAssetNode> nodesById = new LinkedHashMap<>();
        Map<String, LineageDtos.LineageEdgeResponse> edgesById = new LinkedHashMap<>();
        Map<String, Integer> shortestDepthByAssetId = new HashMap<>();
        ArrayDeque<TraversalItem> queue = new ArrayDeque<>();

        nodesById.put(root.assetId(), root);
        shortestDepthByAssetId.put(root.assetId(), 0);
        queue.add(new TraversalItem(root, 0));

        while (!queue.isEmpty()) {
            TraversalItem current = queue.removeFirst();
            if (current.depth() >= boundedDepth) {
                continue;
            }

            List<LineageDtos.LineageEdgeResponse> edges = direction == LineageDirection.DOWN
                    ? lineageRepository.findActiveOutgoing(current.node().assetId())
                    : lineageRepository.findActiveIncoming(current.node().assetId());
            for (LineageDtos.LineageEdgeResponse edge : edges) {
                edgesById.putIfAbsent(edge.edgeId(), edge);
                LineageDtos.LineageAssetNode neighbor = direction == LineageDirection.DOWN
                        ? edge.target()
                        : edge.source();
                nodesById.putIfAbsent(neighbor.assetId(), neighbor);
                int nextDepth = current.depth() + 1;
                Integer knownDepth = shortestDepthByAssetId.get(neighbor.assetId());
                if (knownDepth == null || nextDepth < knownDepth) {
                    shortestDepthByAssetId.put(neighbor.assetId(), nextDepth);
                    queue.addLast(new TraversalItem(neighbor, nextDepth));
                }
            }
        }

        return new LineageDtos.LineageGraphResponse(
                root,
                direction,
                boundedDepth,
                List.copyOf(nodesById.values()),
                List.copyOf(edgesById.values()));
    }

    public LineageDtos.ImpactResponse getImpact(String assetCode, int depth, int recentDays) {
        LineageDtos.LineageGraphResponse downstreamLineage = getLineage(assetCode, LineageDirection.DOWN, depth);
        List<String> impactedAssetIds = downstreamLineage.nodes().stream()
                .map(LineageDtos.LineageAssetNode::assetId)
                .toList();
        List<String> impactedAssetCodes = downstreamLineage.nodes().stream()
                .map(LineageDtos.LineageAssetNode::assetCode)
                .toList();
        Instant since = Instant.now().minus(clampRecentDays(recentDays), ChronoUnit.DAYS);

        return new LineageDtos.ImpactResponse(
                downstreamLineage.root(),
                downstreamLineage.depth(),
                downstreamLineage,
                lineageRepository.findActiveSubscriptionsForAssetIds(impactedAssetIds),
                lineageRepository.findRecentQueriesForAssetCodes(impactedAssetIds, impactedAssetCodes, since, 100));
    }

    private AssetDtos.AssetResponse requireAsset(String assetCode) {
        return assetRepository.findAssetByCode(assetCode)
                .orElseThrow(() -> new AssetNotFoundException(assetCode));
    }

    private LineageDtos.LineageAssetNode toNode(AssetDtos.AssetResponse asset) {
        return new LineageDtos.LineageAssetNode(
                asset.assetId(),
                asset.assetCode(),
                asset.assetName(),
                asset.assetType(),
                asset.engine());
    }

    private LineageDirection parseDirection(String direction) {
        if (direction == null || direction.isBlank()) {
            return LineageDirection.DOWN;
        }
        try {
            return LineageDirection.valueOf(direction.toUpperCase());
        } catch (IllegalArgumentException ex) {
            throw new LineageValidationException("INVALID_LINEAGE_DIRECTION", "Unsupported lineage direction");
        }
    }

    private int clampDepth(int depth) {
        return Math.max(1, Math.min(depth, 10));
    }

    private int clampRecentDays(int recentDays) {
        return Math.max(1, Math.min(recentDays, 365));
    }

    private String newId(String prefix) {
        return prefix + UUID.randomUUID().toString().replace("-", "");
    }

    private record TraversalItem(LineageDtos.LineageAssetNode node, int depth) {
    }
}
