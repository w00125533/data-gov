package io.datagov.common.dto;

import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.NotificationStatus;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class EventDtos {
    private EventDtos() {
    }

    public record CreateAssetEventRequest(
            @NotNull AssetEventType eventType,
            String severity,
            Map<String, Object> payload
    ) {
    }

    public record AssetEventResponse(
            String eventId,
            String assetId,
            String assetCode,
            AssetEventType eventType,
            String severity,
            Map<String, Object> payload,
            Instant createdAt
    ) {
    }

    public record SubscriptionNotificationResponse(
            String notificationId,
            String eventId,
            String subscriptionId,
            String consumerId,
            String consumerName,
            NotificationStatus status,
            String kafkaTopic,
            Instant createdAt,
            Instant sentAt,
            String errorMessage
    ) {
    }

    public record CreateAssetEventResponse(
            AssetEventResponse event,
            List<SubscriptionNotificationResponse> notifications
    ) {
    }

    public record NotificationMessage(
            String notificationId,
            String eventId,
            String assetCode,
            AssetEventType eventType,
            String severity,
            Map<String, Object> payload,
            String subscriptionId,
            String consumerId,
            String consumerName,
            Instant createdAt
    ) {
    }
}
