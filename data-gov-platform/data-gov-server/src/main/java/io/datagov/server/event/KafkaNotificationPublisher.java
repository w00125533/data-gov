package io.datagov.server.event;

import io.datagov.common.dto.EventDtos;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import java.util.concurrent.CompletableFuture;

@Component
public class KafkaNotificationPublisher implements NotificationPublisher {
    private final KafkaTemplate<String, EventDtos.NotificationMessage> kafkaTemplate;

    public KafkaNotificationPublisher(KafkaTemplate<String, EventDtos.NotificationMessage> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    @Override
    public CompletableFuture<Void> publish(String topic, EventDtos.NotificationMessage message) {
        return kafkaTemplate.send(topic, message.notificationId(), message)
                .thenApply(result -> null);
    }
}
