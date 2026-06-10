package io.datagov.sdk;

public class DataGovClientException extends RuntimeException {
    public DataGovClientException(String message, Throwable cause) {
        super(message, cause);
    }
}
