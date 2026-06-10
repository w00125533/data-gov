package io.datagov.server.subscription;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class SubscriptionControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void registerAsset() throws Exception {
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "ads_cell_profile",
                                  "assetName": "ADS Cell Profile",
                                  "assetType": "TABLE",
                                  "engine": "STARROCKS",
                                  "domain": "wireless",
                                  "owner": "network-team",
                                  "description": "Cell profile table",
                                  "lifecycleStatus": "ACTIVE",
                                  "queryable": true,
                                  "federatedQueryable": true,
                                  "fields": [
                                    {
                                      "fieldName": "cell_id",
                                      "fieldType": "varchar",
                                      "ordinalPosition": 1
                                    },
                                    {
                                      "fieldName": "coverage_score",
                                      "fieldType": "double",
                                      "ordinalPosition": 2
                                    }
                                  ],
                                  "physicalBinding": {
                                    "engine": "STARROCKS",
                                    "catalogName": "default_catalog",
                                    "databaseName": "ads",
                                    "tableName": "ads_cell_profile",
                                    "queryAdapter": "starrocks"
                                  }
                                }
                                """))
                .andExpect(status().isOk());
    }

    @Test
    void createListGetAndPatchSubscription() throws Exception {
        String response = mockMvc.perform(post("/api/assets/ads_cell_profile/subscriptions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "environment": "prod"
                                  },
                                  "subscription": {
                                    "assetCode": "ads_cell_profile",
                                    "usageMode": "API_QUERY",
                                    "purpose": "dashboard display",
                                    "fields": ["cell_id", "coverage_score"],
                                    "notifyOn": ["SCHEMA_CHANGE", "DEPRECATION"]
                                  }
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.usageMode").value("API_QUERY"))
                .andExpect(jsonPath("$.declaredFields", hasSize(2)))
                .andExpect(jsonPath("$.notifyOn", hasSize(2)))
                .andExpect(jsonPath("$.lastRuntimeSeenAt", nullValue()))
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andReturn()
                .getResponse()
                .getContentAsString();

        String subscriptionId = com.jayway.jsonpath.JsonPath.read(response, "$.subscriptionId");

        mockMvc.perform(get("/api/subscriptions"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].subscriptionId").value(subscriptionId));

        mockMvc.perform(get("/api/subscriptions/{subscriptionId}", subscriptionId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.purpose").value("dashboard display"));

        mockMvc.perform(patch("/api/subscriptions/{subscriptionId}", subscriptionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "purpose": "dashboard display v2",
                                  "fields": ["cell_id"],
                                  "notifyOn": ["SCHEMA_CHANGE"],
                                  "status": "PAUSED"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.purpose").value("dashboard display v2"))
                .andExpect(jsonPath("$.declaredFields", hasSize(1)))
                .andExpect(jsonPath("$.declaredFields[0]").value("cell_id"))
                .andExpect(jsonPath("$.notifyOn", hasSize(1)))
                .andExpect(jsonPath("$.notifyOn[0]").value("SCHEMA_CHANGE"))
                .andExpect(jsonPath("$.status").value("PAUSED"));
    }

    @Test
    void createSubscriptionRejectsMismatchedBodyAssetCode() throws Exception {
        mockMvc.perform(post("/api/assets/ads_cell_profile/subscriptions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "environment": "prod"
                                  },
                                  "subscription": {
                                    "assetCode": "dwd_session_qos",
                                    "usageMode": "API_QUERY"
                                  }
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("ASSET_CODE_MISMATCH"));
    }

    @Test
    void patchStatusOnlyPreservesExistingDeclarationFields() throws Exception {
        String response = createSubscription();
        String subscriptionId = com.jayway.jsonpath.JsonPath.read(response, "$.subscriptionId");

        mockMvc.perform(patch("/api/subscriptions/{subscriptionId}", subscriptionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "status": "PAUSED"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.purpose").value("dashboard display"))
                .andExpect(jsonPath("$.declaredFields", hasSize(2)))
                .andExpect(jsonPath("$.declaredFields[0]").value("cell_id"))
                .andExpect(jsonPath("$.declaredFields[1]").value("coverage_score"))
                .andExpect(jsonPath("$.notifyOn", hasSize(2)))
                .andExpect(jsonPath("$.notifyOn[0]").value("SCHEMA_CHANGE"))
                .andExpect(jsonPath("$.notifyOn[1]").value("DEPRECATION"))
                .andExpect(jsonPath("$.status").value("PAUSED"));
    }

    @Test
    void malformedStoredSubscriptionJsonReturnsServerError() throws Exception {
        String response = createSubscription();
        String subscriptionId = com.jayway.jsonpath.JsonPath.read(response, "$.subscriptionId");
        jdbcTemplate.update(
                "update subscription set declared_fields = ? where subscription_id = ?",
                "{not-json",
                subscriptionId);

        mockMvc.perform(get("/api/subscriptions/{subscriptionId}", subscriptionId))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.error").value("SUBSCRIPTION_DATA_ACCESS_ERROR"));
    }

    @Test
    void subscribingMissingAssetReturns404() throws Exception {
        mockMvc.perform(post("/api/assets/missing_asset/subscriptions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "environment": "prod"
                                  },
                                  "subscription": {
                                    "assetCode": "missing_asset",
                                    "usageMode": "API_QUERY"
                                  }
                                }
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
    }

    private String createSubscription() throws Exception {
        return mockMvc.perform(post("/api/assets/ads_cell_profile/subscriptions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "environment": "prod"
                                  },
                                  "subscription": {
                                    "assetCode": "ads_cell_profile",
                                    "usageMode": "API_QUERY",
                                    "purpose": "dashboard display",
                                    "fields": ["cell_id", "coverage_score"],
                                    "notifyOn": ["SCHEMA_CHANGE", "DEPRECATION"]
                                  }
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();
    }
}
