package io.datagov.server.query;

public class QueryValidationException extends RuntimeException {
    private final String errorCode;

    public QueryValidationException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    public String getErrorCode() {
        return errorCode;
    }
}
