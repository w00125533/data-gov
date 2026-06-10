package io.datagov.server.lineage;

public class LineageValidationException extends RuntimeException {
    private final String errorCode;

    public LineageValidationException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    public String getErrorCode() {
        return errorCode;
    }
}
