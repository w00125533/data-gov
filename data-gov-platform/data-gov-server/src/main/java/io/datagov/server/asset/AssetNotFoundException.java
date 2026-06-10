package io.datagov.server.asset;

public class AssetNotFoundException extends RuntimeException {
    private final String assetCode;

    public AssetNotFoundException(String assetCode) {
        super("Asset not found: " + assetCode);
        this.assetCode = assetCode;
    }

    public String getAssetCode() {
        return assetCode;
    }
}
