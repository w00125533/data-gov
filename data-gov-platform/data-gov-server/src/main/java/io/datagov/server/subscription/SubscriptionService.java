package io.datagov.server.subscription;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.FormalSubscriptionDtos;
import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.enums.SubscriptionSourceType;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.asset.AssetRepository;
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
    private final AssetRepository assetRepository;

    public SubscriptionService(
            SubscriptionRepository subscriptionRepository,
            TransactionTemplate transactionTemplate,
            AssetRepository assetRepository
    ) {
        this.subscriptionRepository = subscriptionRepository;
        this.transactionTemplate = transactionTemplate;
        this.assetRepository = assetRepository;
    }

    public GovernanceDtos.SubscriptionResponse createSubscription(
            String assetCode,
            GovernanceDtos.CreateSubscriptionRequest request
    ) {
        if (!assetCode.equals(request.subscription().assetCode())) {
            throw new AssetCodeMismatchException(assetCode, request.subscription().assetCode());
        }
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
            if (subscriptionRepository.findSubscription(subscriptionId).isEmpty()) {
                throw new SubscriptionNotFoundException(subscriptionId);
            }
            return subscriptionRepository.updateSubscription(subscriptionId, request, Instant.now());
        });
    }

    public FormalSubscriptionDtos.FormalSubscriptionResponse createFormalSubscription(
            String metadataId,
            FormalSubscriptionDtos.FormalCreateSubscriptionRequest request
    ) {
        AssetDtos.AssetResponse asset = requireAssetById(metadataId);
        GovernanceDtos.SubscriptionDeclarationRequest declaration =
                new GovernanceDtos.SubscriptionDeclarationRequest(
                        asset.assetCode(),
                        request.usageMode(),
                        request.purpose(),
                        request.fields(),
                        request.notifyOn());
        GovernanceDtos.SubscriptionResponse subscription = createSubscription(
                asset.assetCode(),
                new GovernanceDtos.CreateSubscriptionRequest(request.consumer(), declaration));
        return toFormalResponse(metadataId, subscription);
    }

    public FormalSubscriptionDtos.FormalSubscriptionListResponse listFormalSubscriptions(
            String metadataId,
            String consumerId,
            SubscriptionStatus status,
            int page,
            int size
    ) {
        AssetDtos.AssetResponse asset = requireAssetById(metadataId);
        int cappedPage = Math.max(1, page);
        int cappedSize = Math.min(100, Math.max(1, size));
        List<FormalSubscriptionDtos.FormalSubscriptionResponse> items = subscriptionRepository
                .listSubscriptionsForAsset(asset.assetId(), consumerId, status)
                .stream()
                .map(subscription -> toFormalResponse(metadataId, subscription))
                .toList();
        long offset = ((long) cappedPage - 1L) * cappedSize;
        int fromIndex = offset >= items.size() ? items.size() : (int) offset;
        int toIndex = (int) Math.min(items.size(), offset + cappedSize);
        return new FormalSubscriptionDtos.FormalSubscriptionListResponse(
                metadataId,
                items.subList(fromIndex, toIndex),
                cappedPage,
                cappedSize,
                items.size());
    }

    public FormalSubscriptionDtos.FormalCancelSubscriptionResponse cancelFormalSubscriptions(
            String metadataId,
            FormalSubscriptionDtos.FormalCancelSubscriptionRequest request
    ) {
        return transactionTemplate.execute(status -> {
            AssetDtos.AssetResponse asset = requireAssetById(metadataId);
            Instant now = Instant.now();
            List<FormalSubscriptionDtos.CancelledSubscriptionResponse> cancelledSubscriptions =
                    subscriptionRepository.cancelSubscriptionsForAssetAndConsumer(
                                    asset.assetId(),
                                    request.consumerId(),
                                    now)
                            .stream()
                            .map(subscription -> new FormalSubscriptionDtos.CancelledSubscriptionResponse(
                                    subscription.subscriptionId(),
                                    subscription.status()))
                            .toList();
            return new FormalSubscriptionDtos.FormalCancelSubscriptionResponse(
                    metadataId,
                    request.consumerId(),
                    cancelledSubscriptions,
                    now);
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

    private AssetDtos.AssetResponse requireAssetById(String metadataId) {
        return assetRepository.findAssetById(metadataId)
                .orElseThrow(() -> new AssetNotFoundException(metadataId));
    }

    private FormalSubscriptionDtos.FormalSubscriptionResponse toFormalResponse(
            String metadataId,
            GovernanceDtos.SubscriptionResponse subscription
    ) {
        return new FormalSubscriptionDtos.FormalSubscriptionResponse(
                subscription.subscriptionId(),
                metadataId,
                subscription.assetCode(),
                subscription.consumerId(),
                subscription.usageMode(),
                subscription.status(),
                subscription.declaredFields(),
                subscription.notifyOn(),
                subscription.createdAt());
    }

    private String newId(String prefix) {
        return prefix + UUID.randomUUID().toString().replace("-", "");
    }
}
