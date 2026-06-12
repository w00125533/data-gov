package io.datagov.server.drift;

public class DriftDataAccessException extends RuntimeException {
    public DriftDataAccessException(String message, Throwable cause) {
        super(message, cause);
    }
}
