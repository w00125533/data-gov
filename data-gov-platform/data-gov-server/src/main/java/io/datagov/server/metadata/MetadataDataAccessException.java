package io.datagov.server.metadata;

public class MetadataDataAccessException extends RuntimeException {
    public MetadataDataAccessException(String message, Throwable cause) {
        super(message, cause);
    }
}
