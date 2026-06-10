package io.datagov.server.subscription;

public class AssetCodeMismatchException extends RuntimeException {
    private final String pathAssetCode;
    private final String bodyAssetCode;

    public AssetCodeMismatchException(String pathAssetCode, String bodyAssetCode) {
        super("Path assetCode '" + pathAssetCode + "' does not match body assetCode '" + bodyAssetCode + "'");
        this.pathAssetCode = pathAssetCode;
        this.bodyAssetCode = bodyAssetCode;
    }

    public String getPathAssetCode() {
        return pathAssetCode;
    }

    public String getBodyAssetCode() {
        return bodyAssetCode;
    }
}
