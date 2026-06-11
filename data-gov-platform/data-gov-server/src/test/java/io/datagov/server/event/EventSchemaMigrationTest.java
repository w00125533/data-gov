package io.datagov.server.event;

import io.datagov.common.dto.EventDtos;
import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.NotificationStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class EventSchemaMigrationTest {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void eventTablesAndDtosAreAvailable() {
        Integer eventTableCount = jdbcTemplate.queryForObject(
                "select count(*) from information_schema.tables where lower(table_name) = 'asset_event'",
                Integer.class);
        Integer notificationTableCount = jdbcTemplate.queryForObject(
                "select count(*) from information_schema.tables where lower(table_name) = 'subscription_notification'",
                Integer.class);

        EventDtos.NotificationMessage message = new EventDtos.NotificationMessage(
                "ntf_1",
                "evt_1",
                "ads_cell_profile",
                AssetEventType.SCHEMA_CHANGE,
                "WARN",
                Map.of("field", "coverage_score"),
                "sub_1",
                "consumer_1",
                "rno-dashboard",
                Instant.parse("2026-06-11T00:00:00Z"));

        EventDtos.CreateAssetEventResponse response = new EventDtos.CreateAssetEventResponse(
                new EventDtos.AssetEventResponse(
                        "evt_1",
                        "asset_1",
                        "ads_cell_profile",
                        AssetEventType.SCHEMA_CHANGE,
                        "WARN",
                        Map.of("field", "coverage_score"),
                        message.createdAt()),
                List.of(new EventDtos.SubscriptionNotificationResponse(
                        "ntf_1",
                        "evt_1",
                        "sub_1",
                        "consumer_1",
                        "rno-dashboard",
                        NotificationStatus.SENT,
                        "data-gov.subscription-notifications",
                        message.createdAt(),
                        message.createdAt(),
                        null)));

        assertThat(eventTableCount).isEqualTo(1);
        assertThat(notificationTableCount).isEqualTo(1);
        assertThat(response.notifications()).hasSize(1);
        assertThat(message.eventType()).isEqualTo(AssetEventType.SCHEMA_CHANGE);
    }
}
