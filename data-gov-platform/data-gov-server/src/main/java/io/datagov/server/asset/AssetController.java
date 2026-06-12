package io.datagov.server.asset;

import io.datagov.common.dto.AssetDtos;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/assets")
public class AssetController {
    private final AssetService assetService;

    public AssetController(AssetService assetService) {
        this.assetService = assetService;
    }

    @PostMapping("/register")
    public AssetDtos.AssetDetailResponse register(@Valid @RequestBody AssetDtos.RegisterAssetRequest request) {
        return assetService.register(request);
    }

    @PatchMapping("/{assetCode}")
    public AssetDtos.AssetMutationResponse updateAsset(
            @PathVariable("assetCode") String assetCode,
            @Valid @RequestBody AssetDtos.UpdateAssetRequest request
    ) {
        return assetService.updateRuntime(assetCode, request);
    }

    @DeleteMapping("/{assetCode}")
    public AssetDtos.AssetMutationResponse unregisterAsset(
            @PathVariable("assetCode") String assetCode,
            @Valid @RequestBody AssetDtos.UnregisterAssetRequest request
    ) {
        return assetService.unregisterRuntime(assetCode, request);
    }

    @GetMapping
    public List<AssetDtos.AssetResponse> listAssets() {
        return assetService.listAssets();
    }

    @GetMapping("/{assetCode}")
    public AssetDtos.AssetDetailResponse getAsset(@PathVariable("assetCode") String assetCode) {
        return assetService.getAsset(assetCode);
    }

    @GetMapping("/{assetCode}/schema")
    public List<AssetDtos.FieldResponse> getSchema(@PathVariable("assetCode") String assetCode) {
        return assetService.getSchema(assetCode);
    }

    @GetMapping("/{assetCode}/binding")
    public AssetDtos.PhysicalBindingResponse getBinding(@PathVariable("assetCode") String assetCode) {
        return assetService.getBinding(assetCode);
    }
}
