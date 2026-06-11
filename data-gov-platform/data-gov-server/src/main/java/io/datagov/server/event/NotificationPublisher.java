package io.datagov.server.event;

import io.datagov.common.dto.EventDtos;

import java.util.concurrent.CompletableFuture;

public interface NotificationPublisher {
    CompletableFuture<Void> publish(String topic, EventDtos.NotificationMessage message);
}
