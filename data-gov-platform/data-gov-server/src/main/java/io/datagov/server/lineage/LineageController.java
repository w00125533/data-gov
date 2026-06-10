package io.datagov.server.lineage;

import io.datagov.common.dto.LineageDtos;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class LineageController {
    private final LineageService lineageService;

    public LineageController(LineageService lineageService) {
        this.lineageService = lineageService;
    }

    @PostMapping("/lineage/edges")
    public LineageDtos.LineageEdgeResponse createEdge(
            @Valid @RequestBody LineageDtos.CreateLineageEdgeRequest request
    ) {
        return lineageService.createEdge(request);
    }

    @GetMapping("/assets/{assetCode}/lineage")
    public LineageDtos.LineageGraphResponse getLineage(
            @PathVariable("assetCode") String assetCode,
            @RequestParam(name = "direction", defaultValue = "DOWN") String direction,
            @RequestParam(name = "depth", defaultValue = "5") int depth
    ) {
        return lineageService.getLineage(assetCode, direction, depth);
    }

    @GetMapping("/assets/{assetCode}/impact")
    public LineageDtos.ImpactResponse getImpact(
            @PathVariable("assetCode") String assetCode,
            @RequestParam(name = "depth", defaultValue = "5") int depth,
            @RequestParam(name = "recentDays", defaultValue = "30") int recentDays
    ) {
        return lineageService.getImpact(assetCode, depth, recentDays);
    }
}
