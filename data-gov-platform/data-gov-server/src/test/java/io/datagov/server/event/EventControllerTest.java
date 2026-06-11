package io.datagov.server.event;

import io.datagov.common.dto.EventDtos;
import io.datagov.common.enums.AssetEventType;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.List;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentCaptor.forClass;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class EventControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @MockBean
    private NotificationPublisher notificationPublisher;

    @Test
    void eventCreatesNotificationForMatchingActiveSubscriptionAndPublishesKafkaMessage() throws Exception {
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"),
                any(EventDtos.NotificationMessage.class)))
                .thenAnswer(invocation -> {
                    assertThat(TransactionSynchronizationManager.isActualTransactionActive()).isFalse();
                    return CompletableFuture.completedFuture(null);
                });
        registerTableAsset("ads_cell_profile");
        String subscriptionId = createSubscription("ads_cell_profile", "rno-dashboard", "SCHEMA_CHANGE");

        mockMvc.perform(post("/api/assets/ads_cell_profile/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "eventType": "SCHEMA_CHANGE",
                                  "severity": "WARN",
                                  "payload": {
                                    "changedFields": ["coverage_score"]
                                  }
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.event.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.event.eventType").value("SCHEMA_CHANGE"))
                .andExpect(jsonPath("$.notifications", hasSize(1)))
                .andExpect(jsonPath("$.notifications[0].consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.notifications[0].status").value("SENT"));

        Integer sentCount = jdbcTemplate.queryForObject(
                "select count(*) from subscription_notification where status = 'SENT'",
                Integer.class);
        assertThat(sentCount).isEqualTo(1);

        org.mockito.ArgumentCaptor<EventDtos.NotificationMessage> messageCaptor =
                forClass(EventDtos.NotificationMessage.class);
        verify(notificationPublisher, times(1))
                .publish(eq("data-gov.subscription-notifications"), messageCaptor.capture());
        EventDtos.NotificationMessage message = messageCaptor.getValue();
        assertThat(message.notificationId()).startsWith("ntf_");
        assertThat(message.eventId()).startsWith("evt_");
        assertThat(message.assetCode()).isEqualTo("ads_cell_profile");
        assertThat(message.eventType()).isEqualTo(AssetEventType.SCHEMA_CHANGE);
        assertThat(message.severity()).isEqualTo("WARN");
        assertThat(message.payload()).containsEntry("changedFields", List.of("coverage_score"));
        assertThat(message.subscriptionId()).isEqualTo(subscriptionId);
        assertThat(message.consumerId()).startsWith("consumer_");
        assertThat(message.consumerName()).isEqualTo("rno-dashboard");
        assertThat(message.createdAt()).isNotNull();
    }

    @Test
    void eventDoesNotNotifyWhenNotifyOnDoesNotContainEventType() throws Exception {
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"),
                any(EventDtos.NotificationMessage.class)))
                .thenReturn(CompletableFuture.completedFuture(null));
        registerTableAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard", "DEPRECATION");

        mockMvc.perform(post("/api/assets/ads_cell_profile/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "eventType": "SCHEMA_CHANGE"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.notifications", hasSize(0)));

        verify(notificationPublisher, never()).publish(anyString(), any(EventDtos.NotificationMessage.class));
    }

    @Test
    void eventDoesNotNotifyInactiveSubscription() throws Exception {
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"),
                any(EventDtos.NotificationMessage.class)))
                .thenReturn(CompletableFuture.completedFuture(null));
        registerTableAsset("ads_cell_profile");
        String subscriptionId = createSubscription("ads_cell_profile", "rno-dashboard", "SCHEMA_CHANGE");
        jdbcTemplate.update("update subscription set status = 'PAUSED' where subscription_id = ?", subscriptionId);

        mockMvc.perform(post("/api/assets/ads_cell_profile/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "eventType": "SCHEMA_CHANGE"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.notifications", hasSize(0)));

        verify(notificationPublisher, never()).publish(anyString(), any(EventDtos.NotificationMessage.class));
    }

    @Test
    void failedPublishMarksNotificationFailed() throws Exception {
        CompletableFuture<Void> failed = new CompletableFuture<>();
        failed.completeExceptionally(new IllegalStateException("broker unavailable"));
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"),
                any(EventDtos.NotificationMessage.class)))
                .thenReturn(failed);
        registerTableAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard", "SCHEMA_CHANGE");

        mockMvc.perform(post("/api/assets/ads_cell_profile/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "eventType": "SCHEMA_CHANGE"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.notifications", hasSize(1)))
                .andExpect(jsonPath("$.notifications[0].status").value("FAILED"));

        Integer failedCount = jdbcTemplate.queryForObject(
                "select count(*) from subscription_notification where status = 'FAILED' and error_message is not null",
                Integer.class);
        assertThat(failedCount).isEqualTo(1);
    }

    private void registerTableAsset(String assetCode) throws Exception {
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "%s",
                                  "assetName": "%s",
                                  "assetType": "TABLE",
                                  "engine": "STARROCKS",
                                  "lifecycleStatus": "ACTIVE"
                                }
                                """.formatted(assetCode, assetCode)))
                .andExpect(status().isOk());
    }

    private String createSubscription(String assetCode, String consumerName, String notifyOn) throws Exception {
        String body = mockMvc.perform(post("/api/assets/{assetCode}/subscriptions", assetCode)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "%s",
                                    "consumerType": "MICROSERVICE",
                                    "environment": "prod"
                                  },
                                  "subscription": {
                                    "assetCode": "%s",
                                    "usageMode": "API_QUERY",
                                    "notifyOn": ["%s"]
                                  }
                                }
                                """.formatted(consumerName, assetCode, notifyOn)))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();
        return com.jayway.jsonpath.JsonPath.read(body, "$.subscriptionId");
    }
}
