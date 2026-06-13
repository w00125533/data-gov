package io.datagov.server.query;

import com.jayway.jsonpath.JsonPath;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
class FormalQueryControllerTest {
    private static final String BASE_PATH = "/rest/oss/inner/modelengineservice/v1";
    private static final String SUBSCRIPTION_HEADER = "X-DataGov-Subscription-Id";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private FakeStarRocksQueryExecutor executor;

    private String metadataId;
    private String subscriptionId;

    @BeforeEach
    void registerMetadataAndSubscription() throws Exception {
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
                                        },
                                        {
                                          "fieldName": "province",
                                          "fieldType": "varchar",
                                          "ordinal": 3,
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

        subscriptionId = createFormalSubscription("rno-dashboard", List.of("cell_id", "coverage_score"));
    }

    @Test
    void formalApiQueryResolvesMetadataIdAndHeaderSubscription() throws Exception {
        executor.result = new QueryResult(
                List.of("cell_id", "coverage_score"),
                List.of(Map.of("cell_id", "c001", "coverage_score", 98.5)));

        mockMvc.perform(post(BASE_PATH + "/apiquery/{metadataId}", metadataId)
                        .header(SUBSCRIPTION_HEADER, subscriptionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "select": ["cell_id", "coverage_score"],
                                  "filters": [
                                    {"field": "province", "op": "=", "value": "JS"}
                                  ],
                                  "limit": 10
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.queryId", notNullValue()))
                .andExpect(jsonPath("$.columns", hasSize(2)))
                .andExpect(jsonPath("$.rows[0].cell_id").value("c001"))
                .andExpect(jsonPath("$.rowCount").value(1));

        assertThat(executor.calls).hasSize(1);
        assertThat(executor.calls.get(0).sql())
                .isEqualTo("select `cell_id`, `coverage_score` from `default_catalog`.`ads`.`ads_cell_profile` where `province` = ? limit 10");
        assertThat(executor.calls.get(0).params()).containsExactly("JS");

        Map<String, Object> record = queryRecord();
        assertThat(record.get("SUBSCRIPTION_ID")).isEqualTo(subscriptionId);
        assertThat(record.get("REQUEST_TYPE")).isEqualTo("PRODUCT_API");
    }

    @Test
    void formalApiQueryRejectsMismatchedHeaderAndBodySubscription() throws Exception {
        String otherSubscriptionId = createFormalSubscription("rno-dashboard-other", List.of("cell_id"));
        assertThat(otherSubscriptionId).isNotEqualTo(subscriptionId);

        mockMvc.perform(post(BASE_PATH + "/apiquery/{metadataId}", metadataId)
                        .header(SUBSCRIPTION_HEADER, otherSubscriptionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "select": ["cell_id"],
                                  "limit": 5,
                                  "subscriptionId": "%s"
                                }
                                """.formatted(subscriptionId)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("INVALID_SUBSCRIPTION"))
                .andExpect(jsonPath("$.message").value("Subscription header does not match request body"));

        assertThat(executor.calls).isEmpty();
    }

    @Test
    void formalApiQueryAllowsMissingBodyWithHeaderSubscription() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/apiquery/{metadataId}", metadataId)
                        .header(SUBSCRIPTION_HEADER, subscriptionId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.queryId", notNullValue()));

        Map<String, Object> record = queryRecord();
        assertThat(record.get("SUBSCRIPTION_ID")).isEqualTo(subscriptionId);
        assertThat(record.get("REQUEST_TYPE")).isEqualTo("PRODUCT_API");
    }

    @Test
    void formalApiQueryRejectsCancelledSubscription() throws Exception {
        jdbcTemplate.update("update subscription set status = 'CANCELLED' where subscription_id = ?", subscriptionId);

        mockMvc.perform(post(BASE_PATH + "/apiquery/{metadataId}", metadataId)
                        .header(SUBSCRIPTION_HEADER, subscriptionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "select": ["cell_id"],
                                  "limit": 5
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("INVALID_SUBSCRIPTION"))
                .andExpect(jsonPath("$.message").value("Subscription is not active"));

        assertThat(executor.calls).isEmpty();
    }

    @Test
    void formalSqlQueryUsesExistingSqlGateway() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/sqlquery")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sql": "select cell_id from ads_cell_profile",
                                  "limit": 5,
                                  "subscriptionId": "%s"
                                }
                                """.formatted(subscriptionId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.queryId", notNullValue()));

        assertThat(executor.calls).hasSize(1);
        assertThat(executor.calls.get(0).sql())
                .isEqualTo("select cell_id from `default_catalog`.`ads`.`ads_cell_profile` limit 5");

        Map<String, Object> record = queryRecord();
        assertThat(record.get("REQUEST_TYPE")).isEqualTo("SQL_GATEWAY");
        assertThat(record.get("SUBSCRIPTION_ID")).isEqualTo(subscriptionId);
    }

    @Test
    void formalSqlQueryRejectsCancelledSubscription() throws Exception {
        jdbcTemplate.update("update subscription set status = 'CANCELLED' where subscription_id = ?", subscriptionId);

        mockMvc.perform(post(BASE_PATH + "/sqlquery")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sql": "select cell_id from ads_cell_profile",
                                  "limit": 5,
                                  "subscriptionId": "%s"
                                }
                                """.formatted(subscriptionId)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("INVALID_SUBSCRIPTION"))
                .andExpect(jsonPath("$.message").value("Subscription is not active"));

        assertThat(executor.calls).isEmpty();
    }

    @Test
    void formalApiQueryMissingMetadataReturns404() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/apiquery/{metadataId}", "missing_metadata")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "select": ["cell_id"]
                                }
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
    }

    private Map<String, Object> queryRecord() {
        return jdbcTemplate.queryForMap("select * from query_record order by created_at desc limit 1");
    }

    private String createFormalSubscription(String consumerName, List<String> fields) throws Exception {
        String fieldJson = fields.stream()
                .map(field -> "\"" + field + "\"")
                .collect(Collectors.joining(", ", "[", "]"));
        String response = mockMvc.perform(post(BASE_PATH + "/subscriptions/{metadataId}", metadataId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "%s",
                                    "consumerType": "MICROSERVICE",
                                    "owner": "network-team",
                                    "environment": "prod"
                                  },
                                  "usageMode": "API_QUERY",
                                  "purpose": "dashboard display",
                                  "fields": %s,
                                  "notifyOn": ["SCHEMA_CHANGE", "DEPRECATION"],
                                  "notificationStrategy": {
                                    "delivery": "KAFKA",
                                    "sdkCallback": true,
                                    "consumerGroup": "%s"
                                  }
                                }
                                """.formatted(consumerName, fieldJson, consumerName)))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();
        return JsonPath.read(response, "$.subscriptionId");
    }

    @TestConfiguration
    static class FormalQueryTestConfig {
        @Bean
        @Primary
        FakeStarRocksQueryExecutor fakeStarRocksQueryExecutor() {
            return new FakeStarRocksQueryExecutor();
        }
    }

    static class FakeStarRocksQueryExecutor implements StarRocksQueryExecutor {
        private QueryResult result = new QueryResult(List.of("cell_id"), List.of(Map.of("cell_id", "c001")));
        private final List<Call> calls = new ArrayList<>();

        @Override
        public QueryResult execute(String sql, List<Object> params, int maxRows, Duration timeout) {
            calls.add(new Call(sql, List.copyOf(params), maxRows, timeout));
            return result;
        }
    }

    record Call(String sql, List<Object> params, int maxRows, Duration timeout) {
    }
}
