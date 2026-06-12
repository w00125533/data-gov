package io.datagov.server.asset;

import io.datagov.common.dto.EventDtos;
import io.datagov.common.enums.AssetEventType;
import io.datagov.server.event.NotificationPublisher;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentCaptor.forClass;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class AssetRuntimeMutationControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @MockBean
    private NotificationPublisher notificationPublisher;

    @Test
    void patchAssetUpdatesMetadataAndEmitsSchemaChangeNotification() throws Exception {
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"),
                any(EventDtos.NotificationMessage.class)))
                .thenReturn(CompletableFuture.completedFuture(null));
        registerTableAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard", "SCHEMA_CHANGE");

        mockMvc.perform(patch("/api/assets/ads_cell_profile")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetName": "ADS Cell Profile V2",
                                  "description": "Runtime updated profile table",
                                  "fields": [
                                    {
                                      "fieldName": "cell_id",
                                      "fieldType": "varchar",
                                      "ordinalPosition": 1,
                                      "nullable": false,
                                      "primaryKey": true
                                    },
                                    {
                                      "fieldName": "coverage_score",
                                      "fieldType": "double",
                                      "ordinalPosition": 2,
                                      "nullable": true
                                    }
                                  ],
                                  "severity": "WARN"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.asset.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.asset.asset.assetName").value("ADS Cell Profile V2"))
                .andExpect(jsonPath("$.asset.asset.schemaVersion").value(2))
                .andExpect(jsonPath("$.asset.fields", hasSize(2)))
                .andExpect(jsonPath("$.asset.fields[1].fieldName").value("coverage_score"))
                .andExpect(jsonPath("$.event.event.eventType").value("SCHEMA_CHANGE"))
                .andExpect(jsonPath("$.event.event.severity").value("WARN"))
                .andExpect(jsonPath("$.event.notifications", hasSize(1)))
                .andExpect(jsonPath("$.event.notifications[0].status").value("SENT"));

        Integer eventCount = jdbcTemplate.queryForObject(
                "select count(*) from asset_event where event_type = 'SCHEMA_CHANGE'",
                Integer.class);
        Integer notificationCount = jdbcTemplate.queryForObject(
                "select count(*) from subscription_notification where status = 'SENT'",
                Integer.class);
        assertThat(eventCount).isEqualTo(1);
        assertThat(notificationCount).isEqualTo(1);

        ArgumentCaptor<EventDtos.NotificationMessage> messageCaptor =
                forClass(EventDtos.NotificationMessage.class);
        verify(notificationPublisher, times(1))
                .publish(eq("data-gov.subscription-notifications"), messageCaptor.capture());
        EventDtos.NotificationMessage message = messageCaptor.getValue();
        assertThat(message.assetCode()).isEqualTo("ads_cell_profile");
        assertThat(message.eventType()).isEqualTo(AssetEventType.SCHEMA_CHANGE);
        assertThat(message.payload()).containsEntry("operation", "PATCH_ASSET");
        assertThat(message.payload()).containsEntry("changedSections", List.of("asset", "fields"));
    }

    @Test
    void deleteAssetMarksOfflineAndEmitsOfflineNotification() throws Exception {
        when(notificationPublisher.publish(eq("data-gov.subscription-notifications"),
                any(EventDtos.NotificationMessage.class)))
                .thenReturn(CompletableFuture.completedFuture(null));
        registerTableAsset("ads_cell_profile");
        createSubscription("ads_cell_profile", "rno-dashboard", "OFFLINE");

        mockMvc.perform(delete("/api/assets/ads_cell_profile")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "reason": "dataset retired",
                                  "operator": "network-team"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.asset.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.asset.asset.lifecycleStatus").value("OFFLINE"))
                .andExpect(jsonPath("$.asset.asset.queryable").value(false))
                .andExpect(jsonPath("$.asset.asset.federatedQueryable").value(false))
                .andExpect(jsonPath("$.event.event.eventType").value("OFFLINE"))
                .andExpect(jsonPath("$.event.event.severity").value("WARN"))
                .andExpect(jsonPath("$.event.notifications", hasSize(1)))
                .andExpect(jsonPath("$.event.notifications[0].consumerName").value("rno-dashboard"));

        mockMvc.perform(get("/api/assets/ads_cell_profile"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.lifecycleStatus").value("OFFLINE"))
                .andExpect(jsonPath("$.asset.queryable").value(false));

        ArgumentCaptor<EventDtos.NotificationMessage> messageCaptor =
                forClass(EventDtos.NotificationMessage.class);
        verify(notificationPublisher, times(1))
                .publish(eq("data-gov.subscription-notifications"), messageCaptor.capture());
        EventDtos.NotificationMessage message = messageCaptor.getValue();
        assertThat(message.eventType()).isEqualTo(AssetEventType.OFFLINE);
        assertThat(message.payload()).containsEntry("operation", "DELETE_ASSET");
        assertThat(message.payload()).containsEntry("reason", "dataset retired");
        assertThat(message.payload()).containsEntry("operator", "network-team");
    }

    @Test
    void patchUnknownAssetReturns404() throws Exception {
        mockMvc.perform(patch("/api/assets/missing_asset")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetName": "Missing"
                                }
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
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
                                  "domain": "wireless",
                                  "owner": "network-team",
                                  "lifecycleStatus": "ACTIVE",
                                  "queryable": true,
                                  "federatedQueryable": true,
                                  "fields": [
                                    {
                                      "fieldName": "cell_id",
                                      "fieldType": "varchar",
                                      "ordinalPosition": 1,
                                      "nullable": false,
                                      "primaryKey": true
                                    }
                                  ]
                                }
                                """.formatted(assetCode, assetCode)))
                .andExpect(status().isOk());
    }

    private void createSubscription(String assetCode, String consumerName, String notifyOn) throws Exception {
        mockMvc.perform(post("/api/assets/{assetCode}/subscriptions", assetCode)
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
                .andExpect(status().isOk());
    }
}
