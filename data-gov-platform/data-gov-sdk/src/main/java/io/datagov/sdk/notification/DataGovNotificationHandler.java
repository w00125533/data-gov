package io.datagov.sdk.notification;

import io.datagov.common.dto.EventDtos;

@FunctionalInterface
public interface DataGovNotificationHandler {
    void handle(EventDtos.NotificationMessage message);
}
