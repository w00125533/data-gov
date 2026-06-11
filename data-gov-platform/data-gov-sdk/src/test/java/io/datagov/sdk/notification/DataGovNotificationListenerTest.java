package io.datagov.sdk.notification;

import io.datagov.common.dto.EventDtos;
import io.datagov.common.enums.AssetEventType;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DataGovNotificationListenerTest {
    @Test
    void dispatchesMessageToAllHandlers() {
        List<String> seen = new ArrayList<>();
        DataGovNotificationListener listener = new DataGovNotificationListener(List.of(
                message -> seen.add("first:" + message.assetCode()),
                message -> seen.add("second:" + message.eventType().name())
        ));

        listener.onMessage(message());

        assertThat(seen).containsExactly("first:ads_cell_profile", "second:SCHEMA_CHANGE");
    }

    @Test
    void invokesRemainingHandlersWhenOneHandlerFailsThenThrows() {
        List<String> seen = new ArrayList<>();
        DataGovNotificationListener listener = new DataGovNotificationListener(List.of(
                message -> {
                    throw new IllegalStateException("handler failed");
                },
                message -> seen.add(message.notificationId())
        ));

        assertThatThrownBy(() -> listener.onMessage(message()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Failed to handle data governance notification")
                .hasRootCauseMessage("handler failed");
        assertThat(seen).containsExactly("ntf_1");
    }

    @Test
    void recordsFirstHandlerFailureAsCauseAndSuppressesLaterFailures() {
        List<String> seen = new ArrayList<>();
        IllegalStateException firstFailure = new IllegalStateException("first failed");
        IllegalArgumentException secondFailure = new IllegalArgumentException("second failed");
        DataGovNotificationListener listener = new DataGovNotificationListener(List.of(
                message -> {
                    seen.add("first");
                    throw firstFailure;
                },
                message -> {
                    seen.add("second");
                    throw secondFailure;
                },
                message -> seen.add("third")
        ));

        assertThatThrownBy(() -> listener.onMessage(message()))
                .isInstanceOf(IllegalStateException.class)
                .hasCause(firstFailure)
                .satisfies(error -> assertThat(error.getSuppressed()).containsExactly(secondFailure));
        assertThat(seen).containsExactly("first", "second", "third");
    }

    private EventDtos.NotificationMessage message() {
        return new EventDtos.NotificationMessage(
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
    }
}
