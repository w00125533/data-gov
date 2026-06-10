package io.datagov.server.subscription;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.enums.SubscriptionSourceType;
import io.datagov.server.asset.AssetNotFoundException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class SubscriptionService {
    private final SubscriptionRepository subscriptionRepository;
    private final TransactionTemplate transactionTemplate;

    public SubscriptionService(
            SubscriptionRepository subscriptionRepository,
            TransactionTemplate transactionTemplate
    ) {
        this.subscriptionRepository = subscriptionRepository;
        this.transactionTemplate = transactionTemplate;
    }

    public GovernanceDtos.SubscriptionResponse createSubscription(
            String assetCode,
            GovernanceDtos.CreateSubscriptionRequest request
    ) {
        return transactionTemplate.execute(status -> {
            Instant now = Instant.now();
            SubscriptionRepository.AssetRef asset = requireAsset(assetCode);
            GovernanceDtos.ConsumerResponse consumer = subscriptionRepository.upsertConsumer(
                    newId("consumer_"), request.consumer(), null, now);
            return upsertSubscription(asset, consumer.consumerId(), request.subscription(), SubscriptionSourceType.API,
                    null, now);
        });
    }

    public List<GovernanceDtos.SubscriptionResponse> listSubscriptions() {
        return subscriptionRepository.listSubscriptions();
    }

    public GovernanceDtos.SubscriptionResponse getSubscription(String subscriptionId) {
        return subscriptionRepository.findSubscription(subscriptionId)
                .orElseThrow(() -> new SubscriptionNotFoundException(subscriptionId));
    }

    public GovernanceDtos.SubscriptionResponse updateSubscription(
            String subscriptionId,
            GovernanceDtos.UpdateSubscriptionRequest request
    ) {
        return transactionTemplate.execute(status -> {
            GovernanceDtos.SubscriptionResponse current = getSubscription(subscriptionId);
            return subscriptionRepository.updateSubscription(current, request, Instant.now());
        });
    }

    public GovernanceDtos.SdkSubscriptionRegistrationResponse registerSdkSubscriptions(
            GovernanceDtos.SdkSubscriptionRegistrationRequest request
    ) {
        return transactionTemplate.execute(status -> {
            Instant now = Instant.now();
            GovernanceDtos.ConsumerResponse consumer = subscriptionRepository.upsertConsumer(
                    newId("consumer_"), request.consumer(), request.declarationHash(), now);
            List<GovernanceDtos.SubscriptionResponse> subscriptions = request.subscriptions().stream()
                    .map(subscription -> {
                        SubscriptionRepository.AssetRef asset = requireAsset(subscription.assetCode());
                        return upsertSubscription(asset, consumer.consumerId(), subscription,
                                SubscriptionSourceType.SDK_STARTUP, request.declarationHash(), now);
                    })
                    .toList();
            Map<String, String> assetCodeToSubscriptionId = new LinkedHashMap<>();
            for (GovernanceDtos.SubscriptionResponse subscription : subscriptions) {
                assetCodeToSubscriptionId.put(subscription.assetCode(), subscription.subscriptionId());
            }
            return new GovernanceDtos.SdkSubscriptionRegistrationResponse(
                    consumer,
                    subscriptions,
                    assetCodeToSubscriptionId);
        });
    }

    public GovernanceDtos.JobRegistrationResponse registerJob(GovernanceDtos.JobRegistrationRequest request) {
        return transactionTemplate.execute(status -> {
            Instant now = Instant.now();
            validateAssets(request.inputAssets());
            validateAssets(request.outputAssets());
            GovernanceDtos.ConsumerResponse consumer = subscriptionRepository.upsertConsumer(
                    newId("consumer_"), request.consumer(), request.declarationHash(), now);
            List<GovernanceDtos.SubscriptionResponse> subscriptions = request.subscriptions() == null
                    ? List.of()
                    : request.subscriptions().stream()
                    .map(subscription -> {
                        SubscriptionRepository.AssetRef asset = requireAsset(subscription.assetCode());
                        return upsertSubscription(asset, consumer.consumerId(), subscription,
                                SubscriptionSourceType.SDK_STARTUP, request.declarationHash(), now);
                    })
                    .toList();
            SubscriptionRepository.JobRef job = subscriptionRepository.upsertJob(
                    newId("job_"), consumer.consumerId(), request, now);
            return new GovernanceDtos.JobRegistrationResponse(
                    job.jobId(),
                    job.jobName(),
                    job.jobType(),
                    job.status(),
                    consumer,
                    subscriptions,
                    job.lastRegisteredAt());
        });
    }

    private GovernanceDtos.SubscriptionResponse upsertSubscription(
            SubscriptionRepository.AssetRef asset,
            String consumerId,
            GovernanceDtos.SubscriptionDeclarationRequest request,
            SubscriptionSourceType sourceType,
            String declarationHash,
            Instant now
    ) {
        return subscriptionRepository.upsertSubscription(
                newId("sub_"),
                asset.assetId(),
                consumerId,
                request.usageMode(),
                request.purpose(),
                request.fields(),
                request.notifyOn(),
                sourceType,
                declarationHash,
                now);
    }

    private void validateAssets(List<String> assetCodes) {
        if (assetCodes == null) {
            return;
        }
        assetCodes.forEach(this::requireAsset);
    }

    private SubscriptionRepository.AssetRef requireAsset(String assetCode) {
        return subscriptionRepository.findAssetId(assetCode)
                .orElseThrow(() -> new AssetNotFoundException(assetCode));
    }

    private String newId(String prefix) {
        return prefix + UUID.randomUUID().toString().replace("-", "");
    }
}
