package io.datagov.server.lineage;

public class LineageDataAccessException extends RuntimeException {
    public LineageDataAccessException(String message, Throwable cause) {
        super(message, cause);
    }
}
