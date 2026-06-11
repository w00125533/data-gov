package io.datagov.server.event;

public class EventDataAccessException extends RuntimeException {
    public EventDataAccessException(String message, Throwable cause) {
        super(message, cause);
    }
}
