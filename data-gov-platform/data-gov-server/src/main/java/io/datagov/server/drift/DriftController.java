package io.datagov.server.drift;

import io.datagov.common.dto.DriftDtos;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/drift")
public class DriftController {
    private final DriftService driftService;

    public DriftController(DriftService driftService) {
        this.driftService = driftService;
    }

    @PostMapping("/analyze")
    public DriftDtos.DriftAnalysisResponse analyze(
            @RequestBody(required = false) DriftDtos.AnalyzeDriftRequest request) {
        return driftService.analyze(request);
    }

    @GetMapping
    public List<DriftDtos.DriftRecordResponse> listRecords() {
        return driftService.listRecords();
    }
}
