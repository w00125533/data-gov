package io.datagov.server.sdk;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class SdkRegistrationControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @BeforeEach
    void registerAssets() throws Exception {
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "ods_ue_signal",
                                  "assetName": "ODS UE Signal",
                                  "assetType": "STREAM",
                                  "engine": "KAFKA",
                                  "lifecycleStatus": "ACTIVE",
                                  "fields": [
                                    {
                                      "fieldName": "ue_id",
                                      "fieldType": "string",
                                      "ordinalPosition": 1
                                    }
                                  ],
                                  "physicalBinding": {
                                    "engine": "KAFKA",
                                    "topicName": "ods_ue_signal",
                                    "format": "json"
                                  }
                                }
                                """))
                .andExpect(status().isOk());

        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "dwd_session_qos",
                                  "assetName": "DWD Session QoS",
                                  "assetType": "TABLE",
                                  "engine": "HIVE",
                                  "lifecycleStatus": "ACTIVE",
                                  "fields": [
                                    {
                                      "fieldName": "session_id",
                                      "fieldType": "string",
                                      "ordinalPosition": 1
                                    }
                                  ],
                                  "physicalBinding": {
                                    "engine": "HIVE",
                                    "databaseName": "dwd",
                                    "tableName": "dwd_session_qos"
                                  }
                                }
                                """))
                .andExpect(status().isOk());
    }

    @Test
    void sdkRegistersSubscriptionsAtStartup() throws Exception {
        mockMvc.perform(post("/api/sdk/subscriptions/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "environment": "prod"
                                  },
                                  "declarationHash": "sha256:abc",
                                  "subscriptions": [
                                    {
                                      "assetCode": "dwd_session_qos",
                                      "usageMode": "API_QUERY",
                                      "purpose": "dashboard display"
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.consumer.consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.subscriptions", hasSize(1)))
                .andExpect(jsonPath("$.assetCodeToSubscriptionId.dwd_session_qos").exists());
    }

    @Test
    void sdkRegistersFlinkJobDeclarationWithoutRunLifecycle() throws Exception {
        mockMvc.perform(post("/api/sdk/jobs/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "cell-hourly-agg",
                                    "consumerType": "FLINK_JOB",
                                    "environment": "prod"
                                  },
                                  "jobName": "cell-hourly-agg",
                                  "jobType": "FLINK",
                                  "inputAssets": ["ods_ue_signal"],
                                  "outputAssets": ["dwd_session_qos"],
                                  "subscriptions": [
                                    {
                                      "assetCode": "ods_ue_signal",
                                      "usageMode": "FLINK_CONSUME",
                                      "purpose": "hourly aggregation input"
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.jobName").value("cell-hourly-agg"))
                .andExpect(jsonPath("$.jobType").value("FLINK"))
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andExpect(jsonPath("$.subscriptions", hasSize(1)));
    }
}
