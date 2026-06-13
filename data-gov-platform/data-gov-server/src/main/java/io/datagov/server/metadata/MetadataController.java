package io.datagov.server.metadata;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.FormalLineageDtos;
import io.datagov.common.dto.MetadataDtos;
import io.datagov.server.lineage.LineageService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/rest/oss/inner/modelengineservice/v1")
public class MetadataController {
    private final MetadataService metadataService;
    private final LineageService lineageService;

    public MetadataController(MetadataService metadataService, LineageService lineageService) {
        this.metadataService = metadataService;
        this.lineageService = lineageService;
    }

    @PostMapping("/metadata/register")
    public MetadataDtos.MetadataSyncResponse registerSnapshot(
            @Valid @RequestBody MetadataDtos.MetadataSnapshotRegisterRequest request
    ) {
        return metadataService.registerSnapshot(request);
    }

    @GetMapping("/metadata")
    public MetadataDtos.MetadataListResponse listMetadata(
            @RequestParam(name = "keyword", required = false) String keyword,
            @RequestParam(name = "domain", required = false) String domain,
            @RequestParam(name = "metadataType", required = false) String metadataType,
            @RequestParam(name = "owner", required = false) String owner,
            @RequestParam(name = "page", defaultValue = "1") int page,
            @RequestParam(name = "size", defaultValue = "20") int size
    ) {
        return metadataService.listMetadata(keyword, domain, metadataType, owner, page, size);
    }

    @GetMapping("/metadata/{metadataId}")
    public MetadataDtos.MetadataDetailResponse getMetadata(
            @PathVariable("metadataId") String metadataId
    ) {
        return metadataService.getMetadata(metadataId);
    }

    @GetMapping("/metadata/{metadataId}/lineage")
    public FormalLineageDtos.FormalLineageResponse getMetadataLineage(
            @PathVariable("metadataId") String metadataId,
            @RequestParam(name = "direction", defaultValue = "down") String direction,
            @RequestParam(name = "depth", defaultValue = "3") int depth
    ) {
        return lineageService.getFormalMetadataLineage(metadataId, direction, depth);
    }

    @PatchMapping("/metadata/{metadataId}")
    public MetadataDtos.MetadataMutationResponse updateMetadata(
            @PathVariable("metadataId") String metadataId,
            @Valid @RequestBody AssetDtos.UpdateAssetRequest request
    ) {
        return metadataService.updateMetadata(metadataId, request);
    }

    @DeleteMapping("/metadata/{metadataId}")
    public MetadataDtos.MetadataMutationResponse unregisterMetadata(
            @PathVariable("metadataId") String metadataId,
            @Valid @RequestBody AssetDtos.UnregisterAssetRequest request
    ) {
        return metadataService.unregisterMetadata(metadataId, request);
    }
}
