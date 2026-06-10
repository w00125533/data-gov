package io.datagov.server.subscription;

public class SubscriptionDataAccessException extends RuntimeException {
    public SubscriptionDataAccessException(String message, Throwable cause) {
        super(message, cause);
    }
}
