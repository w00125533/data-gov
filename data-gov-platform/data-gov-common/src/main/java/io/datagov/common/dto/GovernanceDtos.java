package io.datagov.common.dto;

import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.JobStatus;
import io.datagov.common.enums.JobType;
import io.datagov.common.enums.SubscriptionSourceType;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.common.enums.UsageMode;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class GovernanceDtos {
    private GovernanceDtos() {
    }

    public record ConsumerRequest(
            @NotBlank String consumerName,
            @NotNull ConsumerType consumerType,
            String owner,
            String environment,
            String runtimeVersion,
            String instanceId
    ) {
    }

    public record ConsumerResponse(
            String consumerId,
            ConsumerType consumerType,
            String consumerName,
            String owner,
            String environment,
            String runtimeVersion,
            String instanceId,
            String declarationHash,
            Instant lastRegisteredAt,
            Instant lastSeenAt
    ) {
    }

    public record SubscriptionDeclarationRequest(
            @NotBlank String assetCode,
            @NotNull UsageMode usageMode,
            String purpose,
            List<String> fields,
            List<AssetEventType> notifyOn
    ) {
    }

    public record CreateSubscriptionRequest(
            @Valid @NotNull ConsumerRequest consumer,
            @Valid @NotNull SubscriptionDeclarationRequest subscription
    ) {
    }

    public record UpdateSubscriptionRequest(
            UsageMode usageMode,
            String purpose,
            List<String> fields,
            List<AssetEventType> notifyOn,
            SubscriptionStatus status
    ) {
    }

    public record SubscriptionResponse(
            String subscriptionId,
            String assetId,
            String assetCode,
            String consumerId,
            String consumerName,
            UsageMode usageMode,
            String purpose,
            List<String> declaredFields,
            List<AssetEventType> notifyOn,
            SubscriptionSourceType sourceType,
            SubscriptionStatus status,
            String declarationHash,
            Instant lastRegisteredAt,
            Instant lastRuntimeSeenAt,
            Instant createdAt,
            Instant updatedAt
    ) {
    }

    public record SdkSubscriptionRegistrationRequest(
            @Valid @NotNull ConsumerRequest consumer,
            String declarationHash,
            @Valid @NotEmpty List<SubscriptionDeclarationRequest> subscriptions
    ) {
    }

    public record SdkSubscriptionRegistrationResponse(
            ConsumerResponse consumer,
            List<SubscriptionResponse> subscriptions,
            Map<String, String> assetCodeToSubscriptionId
    ) {
    }

    public record JobRegistrationRequest(
            @Valid @NotNull ConsumerRequest consumer,
            @NotBlank String jobName,
            @NotNull JobType jobType,
            String owner,
            String codeRef,
            Map<String, Object> runtimeConfig,
            List<String> inputAssets,
            List<String> outputAssets,
            String declarationHash,
            @Valid List<SubscriptionDeclarationRequest> subscriptions
    ) {
    }

    public record JobRegistrationResponse(
            String jobId,
            String jobName,
            JobType jobType,
            JobStatus status,
            ConsumerResponse consumer,
            List<SubscriptionResponse> subscriptions,
            Instant lastRegisteredAt
    ) {
    }
}
