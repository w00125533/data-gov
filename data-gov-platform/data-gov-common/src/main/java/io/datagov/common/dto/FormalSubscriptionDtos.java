package io.datagov.common.dto;

import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.common.enums.UsageMode;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;

public final class FormalSubscriptionDtos {
    private FormalSubscriptionDtos() {
    }

    public record NotificationStrategyRequest(
            String delivery,
            Boolean sdkCallback,
            String consumerGroup
    ) {
    }

    public record FormalCreateSubscriptionRequest(
            @Valid @NotNull GovernanceDtos.ConsumerRequest consumer,
            @NotNull UsageMode usageMode,
            @NotBlank String purpose,
            List<String> fields,
            List<AssetEventType> notifyOn,
            NotificationStrategyRequest notificationStrategy
    ) {
    }

    public record FormalCancelSubscriptionRequest(
            @NotBlank String consumerId,
            @NotBlank String reason,
            @NotBlank String operator
    ) {
    }

    public record FormalSubscriptionResponse(
            String subscriptionId,
            String metadataId,
            String assetCode,
            String consumerId,
            UsageMode usageMode,
            SubscriptionStatus status,
            List<String> fields,
            List<AssetEventType> notifyOn,
            Instant createdAt
    ) {
    }

    public record FormalSubscriptionListResponse(
            String metadataId,
            List<FormalSubscriptionResponse> items,
            int page,
            int size,
            int total
    ) {
    }

    public record CancelledSubscriptionResponse(
            String subscriptionId,
            SubscriptionStatus status
    ) {
    }

    public record FormalCancelSubscriptionResponse(
            String metadataId,
            String consumerId,
            List<CancelledSubscriptionResponse> cancelledSubscriptions,
            Instant cancelledAt
    ) {
    }
}
