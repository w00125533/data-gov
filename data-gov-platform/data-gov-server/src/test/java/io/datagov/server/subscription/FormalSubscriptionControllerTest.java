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
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class FormalSubscriptionControllerTest {
    private static final String BASE_PATH = "/rest/oss/inner/modelengineservice/v1";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    private String metadataId;

    @BeforeEach
    void registerMetadata() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "producer": {
                                    "serviceName": "rno-profile-service",
                                    "serviceType": "MICROSERVICE",
                                    "owner": "network-team",
                                    "environment": "prod",
                                    "instanceId": "pod-1"
                                  },
                                  "syncMode": "FULL",
                                  "metadataList": [
                                    {
                                      "assetCode": "ads_cell_profile",
                                      "assetName": "ADS Cell Profile",
                                      "metadataType": "TABLE",
                                      "sourceType": "STARROCKS",
                                      "domain": "wireless-rno",
                                      "owner": "network-team",
                                      "description": "Formal metadata snapshot item",
                                      "queryable": true,
                                      "federatedQueryable": true,
                                      "schema": [
                                        {
                                          "fieldName": "cell_id",
                                          "fieldType": "varchar",
                                          "ordinal": 1,
                                          "nullable": false
                                        },
                                        {
                                          "fieldName": "coverage_score",
                                          "fieldType": "double",
                                          "ordinal": 2,
                                          "nullable": true
                                        }
                                      ],
                                      "binding": {
                                        "sourceType": "STARROCKS",
                                        "catalog": "default_catalog",
                                        "database": "ads",
                                        "table": "ads_cell_profile",
                                        "queryAdapter": "starrocks"
                                      }
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk());

        metadataId = jdbcTemplate.queryForObject(
                "select asset_id from data_asset where asset_code = ?",
                String.class,
                "ads_cell_profile");
    }

    @Test
    void createListAndCancelFormalSubscriptionByMetadataId() throws Exception {
        String response = mockMvc.perform(post(BASE_PATH + "/subscriptions/{metadataId}", metadataId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validCreateBody()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.subscriptionId", notNullValue()))
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andExpect(jsonPath("$.fields", hasSize(2)))
                .andReturn()
                .getResponse()
                .getContentAsString();

        String subscriptionId = com.jayway.jsonpath.JsonPath.read(response, "$.subscriptionId");
        String consumerId = com.jayway.jsonpath.JsonPath.read(response, "$.consumerId");

        mockMvc.perform(get(BASE_PATH + "/subscriptions/{metadataId}", metadataId)
                        .param("consumerId", consumerId)
                        .param("status", "ACTIVE")
                        .param("page", "1")
                        .param("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].subscriptionId").value(subscriptionId))
                .andExpect(jsonPath("$.items[0].fields[0]").value("cell_id"))
                .andExpect(jsonPath("$.total").value(1));

        mockMvc.perform(delete(BASE_PATH + "/subscriptions/{metadataId}", metadataId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumerId": "%s",
                                  "reason": "no longer needed",
                                  "operator": "network-team"
                                }
                                """.formatted(consumerId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.consumerId").value(consumerId))
                .andExpect(jsonPath("$.cancelledSubscriptions", hasSize(1)))
                .andExpect(jsonPath("$.cancelledSubscriptions[0].subscriptionId").value(subscriptionId))
                .andExpect(jsonPath("$.cancelledSubscriptions[0].status").value("CANCELLED"));

        mockMvc.perform(get(BASE_PATH + "/subscriptions/{metadataId}", metadataId)
                        .param("consumerId", consumerId)
                        .param("status", "CANCELLED")
                        .param("page", "1")
                        .param("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].status").value("CANCELLED"));
    }

    @Test
    void formalSubscriptionMissingMetadataReturns404() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/subscriptions/{metadataId}", "missing_metadata")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(validCreateBody()))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
    }

    private String validCreateBody() {
        return """
                {
                  "consumer": {
                    "consumerName": "rno-dashboard",
                    "consumerType": "MICROSERVICE",
                    "owner": "network-team",
                    "environment": "prod"
                  },
                  "usageMode": "API_QUERY",
                  "purpose": "dashboard display",
                  "fields": ["cell_id", "coverage_score"],
                  "notifyOn": ["SCHEMA_CHANGE", "DEPRECATION"],
                  "notificationStrategy": {
                    "delivery": "KAFKA",
                    "sdkCallback": true,
                    "consumerGroup": "rno-dashboard"
                  }
                }
                """;
    }
}
