package io.datagov.server.query;

public class QueryExecutionException extends RuntimeException {
    private final String errorCode;

    public QueryExecutionException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    public QueryExecutionException(String errorCode, String message, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }

    public String getErrorCode() {
        return errorCode;
    }
}
