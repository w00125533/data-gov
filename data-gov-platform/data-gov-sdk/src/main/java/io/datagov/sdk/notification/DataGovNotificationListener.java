package io.datagov.sdk.notification;

import io.datagov.common.dto.EventDtos;
import org.springframework.kafka.annotation.KafkaListener;

import java.util.List;

public class DataGovNotificationListener {
    private final List<DataGovNotificationHandler> handlers;

    public DataGovNotificationListener(List<DataGovNotificationHandler> handlers) {
        this.handlers = handlers == null ? List.of() : List.copyOf(handlers);
    }

    @KafkaListener(
            topics = "${data-gov.notifications.topic:data-gov.subscription-notifications}",
            groupId = "${data-gov.notifications.group-id:data-gov-sdk}")
    public void onMessage(EventDtos.NotificationMessage message) {
        RuntimeException failure = null;
        for (DataGovNotificationHandler handler : handlers) {
            try {
                handler.handle(message);
            } catch (RuntimeException ex) {
                if (failure == null) {
                    failure = new IllegalStateException("Failed to handle data governance notification", ex);
                } else {
                    failure.addSuppressed(ex);
                }
            }
        }
        if (failure != null) {
            throw failure;
        }
    }
}
