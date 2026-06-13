package io.datagov.server.lineage;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.FormalLineageDtos;
import io.datagov.common.dto.LineageDtos;
import io.datagov.common.dto.MetadataDtos;
import io.datagov.common.enums.LineageDirection;
import io.datagov.common.enums.LineageRelationType;
import io.datagov.common.enums.LineageTransformType;
import io.datagov.common.enums.LineageType;
import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.asset.AssetRepository;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
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

    public void replaceSnapshotLineage(
            MetadataDtos.ProducerRequest producer,
            List<MetadataDtos.MetadataItemRequest> metadataItems,
            Map<String, AssetDtos.AssetResponse> assetsByCode
    ) {
        replaceSnapshotLineage(producer, metadataItems, assetsByCode, assetsByCode);
    }

    public void replaceSnapshotLineage(
            MetadataDtos.ProducerRequest producer,
            List<MetadataDtos.MetadataItemRequest> metadataItems,
            Map<String, AssetDtos.AssetResponse> assetsByCode,
            Map<String, AssetDtos.AssetResponse> lineageScopeAssetsByCode
    ) {
        Instant now = Instant.now();
        List<String> snapshotAssetIds = lineageScopeAssetsByCode.values().stream()
                .map(AssetDtos.AssetResponse::assetId)
                .toList();
        lineageRepository.deactivateProducerEdgesForAssets(snapshotAssetIds, producer.serviceName(), now);

        for (MetadataDtos.MetadataItemRequest item : metadataItems) {
            AssetDtos.AssetResponse currentAsset = requireAssetFromSnapshotOrRepository(assetsByCode, item.assetCode());
            if (item.lineage() == null) {
                continue;
            }

            for (MetadataDtos.MetadataLineageEdgeRequest upstream : safeLineageEdges(item.lineage().upstreams())) {
                AssetDtos.AssetResponse upstreamAsset = requireAssetFromSnapshotOrRepository(
                        assetsByCode,
                        upstream.assetCode());
                createSnapshotEdge(upstreamAsset, currentAsset, producer, upstream, now);
            }

            for (MetadataDtos.MetadataLineageEdgeRequest downstream : safeLineageEdges(item.lineage().downstreams())) {
                AssetDtos.AssetResponse downstreamAsset = requireAssetFromSnapshotOrRepository(
                        assetsByCode,
                        downstream.assetCode());
                createSnapshotEdge(currentAsset, downstreamAsset, producer, downstream, now);
            }
        }
    }

    public LineageDtos.LineageGraphResponse getLineage(String assetCode, String direction, int depth) {
        return getLineage(assetCode, parseDirection(direction), depth);
    }

    public FormalLineageDtos.FormalLineageResponse getFormalMetadataLineage(
            String metadataId,
            String direction,
            int depth
    ) {
        AssetDtos.AssetResponse asset = assetRepository.findAssetById(metadataId)
                .orElseThrow(() -> new AssetNotFoundException(metadataId));
        LineageDtos.LineageGraphResponse graph = getLineage(asset.assetCode(), direction, depth);
        List<String> lineageEdgeIds = graph.edges().stream()
                .map(LineageDtos.LineageEdgeResponse::edgeId)
                .toList();
        Map<String, List<LineageRepository.FieldLineageView>> fieldEdgesByLineageId =
                groupFieldEdgesByLineageId(lineageRepository.findActiveFieldEdgesForLineageIds(lineageEdgeIds));

        return new FormalLineageDtos.FormalLineageResponse(
                metadataId,
                graph.direction(),
                graph.depth(),
                graph.nodes().stream()
                        .map(this::toFormalNode)
                        .toList(),
                graph.edges().stream()
                        .map(edge -> toFormalEdge(edge, graph.direction()))
                        .toList(),
                graph.edges().stream()
                        .flatMap(edge -> fieldEdgesByLineageId
                                .getOrDefault(edge.edgeId(), List.of())
                                .stream()
                                .map(fieldEdge -> toFormalFieldEdge(edge, fieldEdge, graph.direction())))
                        .toList());
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

    private List<MetadataDtos.MetadataLineageEdgeRequest> safeLineageEdges(
            List<MetadataDtos.MetadataLineageEdgeRequest> lineageEdges
    ) {
        return lineageEdges == null ? List.of() : lineageEdges;
    }

    private List<MetadataDtos.MetadataFieldMappingRequest> safeFieldMappings(
            List<MetadataDtos.MetadataFieldMappingRequest> fieldMappings
    ) {
        return fieldMappings == null ? List.of() : fieldMappings;
    }

    private AssetDtos.AssetResponse requireAssetFromSnapshotOrRepository(
            Map<String, AssetDtos.AssetResponse> assetsByCode,
            String assetCode
    ) {
        AssetDtos.AssetResponse asset = assetsByCode.get(assetCode);
        return asset == null ? requireAsset(assetCode) : asset;
    }

    private LineageDtos.LineageEdgeResponse createSnapshotEdge(
            AssetDtos.AssetResponse source,
            AssetDtos.AssetResponse target,
            MetadataDtos.ProducerRequest producer,
            MetadataDtos.MetadataLineageEdgeRequest request,
            Instant now
    ) {
        if (source.assetId().equals(target.assetId())) {
            throw new LineageValidationException(
                    "INVALID_LINEAGE_EDGE",
                    "Lineage edge source and target must be different assets");
        }

        LineageType lineageType = request.lineageType() == null ? LineageType.TABLE : request.lineageType();
        LineageTransformType transformType = request.transformType() == null
                ? LineageTransformType.DIRECT
                : request.transformType();
        Map<String, Object> properties = Map.of(
                "lineageType", lineageType.name(),
                "transformType", transformType.name());
        LineageDtos.LineageEdgeResponse edge = new LineageDtos.LineageEdgeResponse(
                newId("lin_"),
                toNode(source),
                toNode(target),
                LineageRelationType.DERIVES,
                producer.serviceName(),
                request.processName(),
                request.jobName(),
                request.expression(),
                properties,
                true,
                now,
                now);
        lineageRepository.insertEdge(edge);

        if (lineageType == LineageType.FIELD) {
            for (MetadataDtos.MetadataFieldMappingRequest fieldMapping : safeFieldMappings(request.fieldMappings())) {
                lineageRepository.insertFieldEdge(new LineageRepository.FieldLineageRecord(
                        newId("lfe_"),
                        edge.edgeId(),
                        requireFieldId(source.assetId(), fieldMapping.sourceField()),
                        requireFieldId(target.assetId(), fieldMapping.targetField()),
                        fieldMapping.expression(),
                        request.expression(),
                        properties,
                        now,
                        now));
            }
        }

        return edge;
    }

    private String requireFieldId(String assetId, String fieldName) {
        return assetRepository.findFields(assetId).stream()
                .filter(field -> field.fieldName().equals(fieldName))
                .map(AssetDtos.FieldResponse::fieldId)
                .findFirst()
                .orElseThrow(() -> new LineageValidationException(
                        "UNKNOWN_LINEAGE_FIELD",
                        "Unknown lineage field: " + fieldName));
    }

    private LineageDtos.LineageAssetNode toNode(AssetDtos.AssetResponse asset) {
        return new LineageDtos.LineageAssetNode(
                asset.assetId(),
                asset.assetCode(),
                asset.assetName(),
                asset.assetType(),
                asset.engine());
    }

    private FormalLineageDtos.FormalLineageNode toFormalNode(LineageDtos.LineageAssetNode node) {
        return new FormalLineageDtos.FormalLineageNode(
                node.assetId(),
                node.assetCode(),
                node.assetName());
    }

    private FormalLineageDtos.FormalLineageEdge toFormalEdge(
            LineageDtos.LineageEdgeResponse edge,
            LineageDirection direction
    ) {
        return new FormalLineageDtos.FormalLineageEdge(
                edge.source().assetId(),
                edge.source().assetCode(),
                edge.target().assetId(),
                edge.target().assetCode(),
                lineageType(edge),
                direction,
                edge.description());
    }

    private FormalLineageDtos.FormalFieldLineageEdge toFormalFieldEdge(
            LineageDtos.LineageEdgeResponse edge,
            LineageRepository.FieldLineageView fieldEdge,
            LineageDirection direction
    ) {
        return new FormalLineageDtos.FormalFieldLineageEdge(
                edge.source().assetId(),
                edge.source().assetCode(),
                fieldEdge.sourceField(),
                edge.target().assetId(),
                edge.target().assetCode(),
                fieldEdge.targetField(),
                LineageType.FIELD,
                direction,
                fieldEdge.expression());
    }

    private Map<String, List<LineageRepository.FieldLineageView>> groupFieldEdgesByLineageId(
            List<LineageRepository.FieldLineageView> fieldEdges
    ) {
        Map<String, List<LineageRepository.FieldLineageView>> fieldEdgesByLineageId = new LinkedHashMap<>();
        for (LineageRepository.FieldLineageView fieldEdge : fieldEdges) {
            fieldEdgesByLineageId
                    .computeIfAbsent(fieldEdge.lineageEdgeId(), ignored -> new ArrayList<>())
                    .add(fieldEdge);
        }
        return fieldEdgesByLineageId;
    }

    private LineageType lineageType(LineageDtos.LineageEdgeResponse edge) {
        Object value = edge.properties().get("lineageType");
        if (value instanceof String lineageType && !lineageType.isBlank()) {
            try {
                return LineageType.valueOf(lineageType.trim().toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException ex) {
                return LineageType.TABLE;
            }
        }
        return LineageType.TABLE;
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
