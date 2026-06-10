package io.datagov.server.asset;

import io.datagov.common.dto.AssetDtos;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
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
