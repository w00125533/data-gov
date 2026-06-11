package io.datagov.server.event;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.EventDtos;
import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.asset.AssetRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicReference;

@Service
public class EventService {
    private final AssetRepository assetRepository;
    private final EventRepository eventRepository;
    private final NotificationPublisher notificationPublisher;
    private final NotificationProperties notificationProperties;
    private final TransactionTemplate transactionTemplate;
    private final TransactionTemplate notificationUpdateTransactionTemplate;

    public EventService(
            AssetRepository assetRepository,
            EventRepository eventRepository,
            NotificationPublisher notificationPublisher,
            NotificationProperties notificationProperties,
            TransactionTemplate transactionTemplate
    ) {
        this.assetRepository = assetRepository;
        this.eventRepository = eventRepository;
        this.notificationPublisher = notificationPublisher;
        this.notificationProperties = notificationProperties;
        this.transactionTemplate = transactionTemplate;
        this.notificationUpdateTransactionTemplate = new TransactionTemplate(transactionTemplate.getTransactionManager());
        this.notificationUpdateTransactionTemplate.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }

    public EventDtos.CreateAssetEventResponse createEvent(
            String assetCode,
            EventDtos.CreateAssetEventRequest request
    ) {
        PersistedEvent persisted = transactionTemplate.execute(status -> persistEvent(assetCode, request));
        return new EventDtos.CreateAssetEventResponse(
                persisted.event(),
                publishNotifications(persisted.event(), persisted.notifications()));
    }

    private PersistedEvent persistEvent(
            String assetCode,
            EventDtos.CreateAssetEventRequest request
    ) {
        AssetDtos.AssetResponse asset = assetRepository.findAssetByCode(assetCode)
                .orElseThrow(() -> new AssetNotFoundException(assetCode));
        Instant now = Instant.now();
        EventDtos.AssetEventResponse event = eventRepository.insertEvent(
                newId("evt_"), asset, request, now);
        String topic = notificationProperties.topic();

        List<EventDtos.SubscriptionNotificationResponse> notifications = new ArrayList<>();
        for (EventRepository.MatchingSubscription subscription
                : eventRepository.findMatchingSubscriptions(asset.assetId(), request.eventType())) {
            notifications.add(eventRepository.insertNotification(
                    newId("ntf_"), event.eventId(), subscription, topic, now));
        }

        return new PersistedEvent(event, List.copyOf(notifications));
    }

    private List<EventDtos.SubscriptionNotificationResponse> publishNotifications(
            EventDtos.AssetEventResponse event,
            List<EventDtos.SubscriptionNotificationResponse> notifications
    ) {
        List<EventDtos.SubscriptionNotificationResponse> publishedNotifications = new ArrayList<>();
        for (EventDtos.SubscriptionNotificationResponse notification : notifications) {
            publishedNotifications.add(publishAndMark(event, notification));
        }
        return List.copyOf(publishedNotifications);
    }

    private EventDtos.SubscriptionNotificationResponse publishAndMark(
            EventDtos.AssetEventResponse event,
            EventDtos.SubscriptionNotificationResponse notification
    ) {
        EventDtos.NotificationMessage message = new EventDtos.NotificationMessage(
                notification.notificationId(),
                event.eventId(),
                event.assetCode(),
                event.eventType(),
                event.severity(),
                event.payload(),
                notification.subscriptionId(),
                notification.consumerId(),
                notification.consumerName(),
                notification.createdAt());
        AtomicReference<EventDtos.SubscriptionNotificationResponse> currentStatus =
                new AtomicReference<>(notification);
        try {
            CompletableFuture<Void> future = notificationPublisher.publish(notification.kafkaTopic(), message);
            if (future == null) {
                return markNotificationFailed(notification.notificationId(), "Publisher returned null future");
            }
            future.whenComplete((ignored, ex) -> {
                if (ex == null) {
                    currentStatus.set(markNotificationSent(notification.notificationId(), Instant.now()));
                } else {
                    currentStatus.set(markNotificationFailed(notification.notificationId(), errorMessage(ex)));
                }
            });
            return currentStatus.get();
        } catch (CompletionException ex) {
            return markNotificationFailed(notification.notificationId(), errorMessage(ex));
        } catch (RuntimeException ex) {
            return markNotificationFailed(notification.notificationId(), errorMessage(ex));
        }
    }

    private EventDtos.SubscriptionNotificationResponse markNotificationSent(String notificationId, Instant sentAt) {
        return notificationUpdateTransactionTemplate.execute(status ->
                eventRepository.markNotificationSent(notificationId, sentAt));
    }

    private EventDtos.SubscriptionNotificationResponse markNotificationFailed(String notificationId, String errorMessage) {
        return notificationUpdateTransactionTemplate.execute(status ->
                eventRepository.markNotificationFailed(notificationId, errorMessage));
    }

    private String errorMessage(Throwable ex) {
        Throwable cause = ex instanceof CompletionException && ex.getCause() != null ? ex.getCause() : ex;
        return cause.getMessage() == null ? cause.getClass().getName() : cause.getMessage();
    }

    private String newId(String prefix) {
        return prefix + UUID.randomUUID().toString().replace("-", "");
    }

    private record PersistedEvent(
            EventDtos.AssetEventResponse event,
            List<EventDtos.SubscriptionNotificationResponse> notifications
    ) {
    }
}
