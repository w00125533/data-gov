package io.datagov.server.event;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.EventDtos;
import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.NotificationStatus;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Map;

@Repository
public class EventRepository {
    private static final TypeReference<Map<String, Object>> PAYLOAD_TYPE = new TypeReference<>() {
    };

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public EventRepository(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public EventDtos.AssetEventResponse insertEvent(
            String eventId,
            AssetDtos.AssetResponse asset,
            EventDtos.CreateAssetEventRequest request,
            Instant now
    ) {
        try {
            jdbcTemplate.update("""
                    insert into asset_event (
                        event_id, asset_id, event_type, event_payload, severity, created_at
                    ) values (?, ?, ?, ?, ?, ?)
                    """,
                    eventId,
                    asset.assetId(),
                    request.eventType().name(),
                    writePayload(request.payload()),
                    request.severity(),
                    Timestamp.from(now));
            return new EventDtos.AssetEventResponse(
                    eventId,
                    asset.assetId(),
                    asset.assetCode(),
                    request.eventType(),
                    request.severity(),
                    request.payload() == null ? Map.of() : request.payload(),
                    now);
        } catch (DataAccessException ex) {
            throw new EventDataAccessException("Failed to insert asset event", ex);
        }
    }

    public List<MatchingSubscription> findMatchingSubscriptions(String assetId, AssetEventType eventType) {
        try {
            return jdbcTemplate.query("""
                    select s.subscription_id, s.consumer_id, c.consumer_name
                    from subscription s
                    join consumer c on c.consumer_id = s.consumer_id
                    where s.asset_id = ?
                      and s.status = 'ACTIVE'
                      and s.notify_on like ? escape '\\'
                    order by s.created_at, s.subscription_id
                    """,
                    (rs, rowNum) -> new MatchingSubscription(
                            rs.getString("subscription_id"),
                            rs.getString("consumer_id"),
                            rs.getString("consumer_name")),
                    assetId,
                    "%\"" + escapeLike(eventType.name()) + "\"%");
        } catch (DataAccessException ex) {
            throw new EventDataAccessException("Failed to find matching event subscriptions", ex);
        }
    }

    public EventDtos.SubscriptionNotificationResponse insertNotification(
            String notificationId,
            String eventId,
            MatchingSubscription subscription,
            String topic,
            Instant now
    ) {
        try {
            jdbcTemplate.update("""
                    insert into subscription_notification (
                        notification_id, event_id, subscription_id, consumer_id, status, kafka_topic,
                        error_message, created_at, sent_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    notificationId,
                    eventId,
                    subscription.subscriptionId(),
                    subscription.consumerId(),
                    NotificationStatus.PENDING.name(),
                    topic,
                    null,
                    Timestamp.from(now),
                    null);
            return findNotification(notificationId);
        } catch (DataAccessException ex) {
            throw new EventDataAccessException("Failed to insert subscription notification", ex);
        }
    }

    public EventDtos.SubscriptionNotificationResponse markNotificationSent(String notificationId, Instant sentAt) {
        try {
            jdbcTemplate.update("""
                    update subscription_notification
                    set status = ?, sent_at = ?, error_message = null
                    where notification_id = ?
                    """, NotificationStatus.SENT.name(), Timestamp.from(sentAt), notificationId);
            return findNotification(notificationId);
        } catch (DataAccessException ex) {
            throw new EventDataAccessException("Failed to mark subscription notification sent", ex);
        }
    }

    public EventDtos.SubscriptionNotificationResponse markNotificationFailed(
            String notificationId,
            String errorMessage
    ) {
        try {
            jdbcTemplate.update("""
                    update subscription_notification
                    set status = ?, error_message = ?
                    where notification_id = ?
                    """, NotificationStatus.FAILED.name(), errorMessage, notificationId);
            return findNotification(notificationId);
        } catch (DataAccessException ex) {
            throw new EventDataAccessException("Failed to mark subscription notification failed", ex);
        }
    }

    private EventDtos.SubscriptionNotificationResponse findNotification(String notificationId) {
        return jdbcTemplate.queryForObject("""
                select n.notification_id, n.event_id, n.subscription_id, n.consumer_id, c.consumer_name,
                       n.status, n.kafka_topic, n.created_at, n.sent_at, n.error_message
                from subscription_notification n
                join consumer c on c.consumer_id = n.consumer_id
                where n.notification_id = ?
                """, notificationMapper(), notificationId);
    }

    private RowMapper<EventDtos.SubscriptionNotificationResponse> notificationMapper() {
        return (rs, rowNum) -> new EventDtos.SubscriptionNotificationResponse(
                rs.getString("notification_id"),
                rs.getString("event_id"),
                rs.getString("subscription_id"),
                rs.getString("consumer_id"),
                rs.getString("consumer_name"),
                NotificationStatus.valueOf(rs.getString("status")),
                rs.getString("kafka_topic"),
                rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("sent_at") == null ? null : rs.getTimestamp("sent_at").toInstant(),
                rs.getString("error_message"));
    }

    private String writePayload(Map<String, Object> payload) {
        try {
            return objectMapper.writeValueAsString(payload == null ? Map.of() : payload);
        } catch (Exception ex) {
            throw new EventDataAccessException("Failed to serialize asset event payload", ex);
        }
    }

    @SuppressWarnings("unused")
    private Map<String, Object> readPayload(String payload) {
        if (payload == null || payload.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(payload, PAYLOAD_TYPE);
        } catch (Exception ex) {
            throw new EventDataAccessException("Failed to deserialize asset event payload", ex);
        }
    }

    private String escapeLike(String value) {
        return value
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_");
    }

    public record MatchingSubscription(
            String subscriptionId,
            String consumerId,
            String consumerName
    ) {
    }
}
