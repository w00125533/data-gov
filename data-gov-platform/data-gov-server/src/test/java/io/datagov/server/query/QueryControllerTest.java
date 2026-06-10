package io.datagov.server.query;

import com.fasterxml.jackson.databind.ObjectMapper;
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

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.greaterThan;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
class QueryControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private FakeStarRocksQueryExecutor executor;

    @Autowired
    private ObjectMapper objectMapper;

    @BeforeEach
    void registerAssets() throws Exception {
        registerAsset("ads_cell_profile", "STARROCKS", true, true, "default_catalog", "ads", "ads_cell_profile",
                List.of("cell_id", "coverage_score", "province"));
        registerAsset("dwd_session_qos", "HIVE", true, true, "hive_catalog", "dwd", "dwd_session_qos",
                List.of("cell_id", "qos_score"));
        registerAsset("ods_ue_signal", "KAFKA", true, true, null, null, null,
                List.of("ue_id"));
    }

    @Test
    void productApiExecutesQueryAndRecordsSuccess() throws Exception {
        executor.result = new QueryResult(
                List.of("cell_id", "coverage_score"),
                List.of(Map.of("cell_id", "c001", "coverage_score", 98.5)));

        mockMvc.perform(post("/api/assets/ads_cell_profile/query")
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
                .andExpect(jsonPath("$.rowCount").value(1))
                .andExpect(jsonPath("$.elapsedMs", greaterThan(-1)));

        org.assertj.core.api.Assertions.assertThat(executor.calls).hasSize(1);
        org.assertj.core.api.Assertions.assertThat(executor.calls.get(0).sql())
                .isEqualTo("select `cell_id`, `coverage_score` from `default_catalog`.`ads`.`ads_cell_profile` where `province` = ? limit 10");
        org.assertj.core.api.Assertions.assertThat(executor.calls.get(0).params()).containsExactly("JS");

        Map<String, Object> record = queryRecord();
        org.assertj.core.api.Assertions.assertThat(record.get("REQUEST_TYPE")).isEqualTo("PRODUCT_API");
        org.assertj.core.api.Assertions.assertThat(record.get("STATUS")).isEqualTo("SUCCESS");
        org.assertj.core.api.Assertions.assertThat(record.get("ROW_COUNT")).isEqualTo(1);
        org.assertj.core.api.Assertions.assertThat(record.get("REWRITTEN_SQL").toString()).contains("default_catalog");
    }

    @Test
    void productApiRejectsUnknownSelectedField() throws Exception {
        mockMvc.perform(post("/api/assets/ads_cell_profile/query")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "select": ["missing_field"]
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("UNKNOWN_FIELD"));

        Map<String, Object> record = queryRecord();
        org.assertj.core.api.Assertions.assertThat(record.get("STATUS")).isEqualTo("FAILED");
        org.assertj.core.api.Assertions.assertThat(record.get("ERROR_CODE")).isEqualTo("UNKNOWN_FIELD");
    }

    @Test
    void productApiRejectsKafkaAsset() throws Exception {
        mockMvc.perform(post("/api/assets/ods_ue_signal/query")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("KAFKA_QUERY_NOT_SUPPORTED"));
    }

    @Test
    void productApiUpdatesSubscriptionRuntimeTimestampAfterRecordedAttempt() throws Exception {
        String subscriptionId = createSubscription();

        mockMvc.perform(post("/api/assets/ads_cell_profile/query")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "select": ["cell_id"],
                                  "subscriptionId": "%s"
                                }
                                """.formatted(subscriptionId)))
                .andExpect(status().isOk());

        Map<String, Object> record = queryRecord();
        org.assertj.core.api.Assertions.assertThat(record.get("SUBSCRIPTION_ID")).isEqualTo(subscriptionId);
        Integer timestamps = jdbcTemplate.queryForObject(
                "select count(*) from subscription where subscription_id = ? and last_runtime_seen_at is not null",
                Integer.class,
                subscriptionId);
        org.assertj.core.api.Assertions.assertThat(timestamps).isEqualTo(1);
    }

    @Test
    void sqlGatewayRejectsDelete() throws Exception {
        mockMvc.perform(post("/api/sql")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sql": "delete from ads_cell_profile where cell_id = 'c001'"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("INVALID_SQL"));

        Map<String, Object> record = queryRecord();
        org.assertj.core.api.Assertions.assertThat(record.get("STATUS")).isEqualTo("FAILED");
        org.assertj.core.api.Assertions.assertThat(record.get("ERROR_CODE")).isEqualTo("INVALID_SQL");
        org.assertj.core.api.Assertions.assertThat(record.get("REFERENCED_ASSET_CODES").toString())
                .isEqualTo("[\"ads_cell_profile\"]");
    }

    @Test
    void sqlGatewayRewritesAssetCodeToPhysicalName() throws Exception {
        mockMvc.perform(post("/api/sql")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sql": "select cell_id from ads_cell_profile",
                                  "limit": 5
                                }
                                """))
                .andExpect(status().isOk());

        org.assertj.core.api.Assertions.assertThat(executor.calls).hasSize(1);
        org.assertj.core.api.Assertions.assertThat(executor.calls.get(0).sql())
                .isEqualTo("select cell_id from `default_catalog`.`ads`.`ads_cell_profile` limit 5");
        Map<String, Object> record = queryRecord();
        org.assertj.core.api.Assertions.assertThat(record.get("REFERENCED_ASSET_CODES").toString())
                .isEqualTo("[\"ads_cell_profile\"]");
    }

    @Test
    void sqlGatewaySupportsSimpleTwoAssetJoin() throws Exception {
        mockMvc.perform(post("/api/sql")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sql": "select a.cell_id, b.qos_score from ads_cell_profile a join dwd_session_qos b on a.cell_id = b.cell_id",
                                  "limit": 20
                                }
                                """))
                .andExpect(status().isOk());

        org.assertj.core.api.Assertions.assertThat(executor.calls.get(0).sql())
                .contains("from `default_catalog`.`ads`.`ads_cell_profile` a join `hive_catalog`.`dwd`.`dwd_session_qos` b");
        Map<String, Object> record = queryRecord();
        org.assertj.core.api.Assertions.assertThat(record.get("REFERENCED_ASSET_CODES").toString())
                .isEqualTo("[\"ads_cell_profile\",\"dwd_session_qos\"]");
    }

    @Test
    void sqlGatewaySupportsSimpleCteReferencingRegisteredAsset() throws Exception {
        mockMvc.perform(post("/api/sql")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sql": "with q as (select cell_id from ads_cell_profile) select cell_id from q",
                                  "limit": 10
                                }
                                """))
                .andExpect(status().isOk());

        org.assertj.core.api.Assertions.assertThat(executor.calls.get(0).sql())
                .isEqualTo("with q as (select cell_id from `default_catalog`.`ads`.`ads_cell_profile`) select cell_id from q limit 10");
        Map<String, Object> record = queryRecord();
        org.assertj.core.api.Assertions.assertThat(record.get("REFERENCED_ASSET_CODES").toString())
                .isEqualTo("[\"ads_cell_profile\"]");
    }

    @Test
    void sqlGatewayRejectsJoinWhenAnyAssetIsNotFederatedQueryable() throws Exception {
        registerAsset("dim_local_only", "STARROCKS", true, false, "default_catalog", "dim", "dim_local_only",
                List.of("cell_id", "region"));

        mockMvc.perform(post("/api/sql")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sql": "select a.cell_id, d.region from ads_cell_profile a join dim_local_only d on a.cell_id = d.cell_id",
                                  "limit": 20
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_QUERYABLE"));

        Map<String, Object> record = queryRecord();
        org.assertj.core.api.Assertions.assertThat(record.get("STATUS")).isEqualTo("FAILED");
        org.assertj.core.api.Assertions.assertThat(record.get("REFERENCED_ASSET_CODES").toString())
                .isEqualTo("[\"ads_cell_profile\",\"dim_local_only\"]");
    }

    @Test
    void sqlGatewayRejectsUnknownAssetCode() throws Exception {
        mockMvc.perform(post("/api/sql")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sql": "select id from missing_asset"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("UNKNOWN_SQL_ASSET"))
                .andExpect(jsonPath("$.message", containsString("missing_asset")));
    }

    private void registerAsset(
            String assetCode,
            String engine,
            boolean queryable,
            boolean federatedQueryable,
            String catalog,
            String database,
            String table,
            List<String> fields
    ) throws Exception {
        String fieldJson = objectMapper.writeValueAsString(fields.stream()
                .map(field -> Map.of("fieldName", field, "fieldType", "varchar"))
                .toList());
        String bindingJson = "KAFKA".equals(engine)
                ? """
                  {
                    "engine": "KAFKA",
                    "topicName": "%s",
                    "format": "json"
                  }
                  """.formatted(assetCode)
                : """
                  {
                    "engine": "%s",
                    "catalogName": "%s",
                    "databaseName": "%s",
                    "tableName": "%s",
                    "queryAdapter": "starrocks"
                  }
                  """.formatted(engine, catalog, database, table);

        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "%s",
                                  "assetName": "%s",
                                  "assetType": "TABLE",
                                  "engine": "%s",
                                  "lifecycleStatus": "ACTIVE",
                                  "queryable": %s,
                                  "federatedQueryable": %s,
                                  "fields": %s,
                                  "physicalBinding": %s
                                }
                                """.formatted(assetCode, assetCode, engine, queryable, federatedQueryable, fieldJson,
                                bindingJson)))
                .andExpect(status().isOk());
    }

    private String createSubscription() throws Exception {
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
                                    "fields": ["cell_id"]
                                  }
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();
        return com.jayway.jsonpath.JsonPath.read(response, "$.subscriptionId");
    }

    private Map<String, Object> queryRecord() {
        return jdbcTemplate.queryForMap("select * from query_record order by created_at desc limit 1");
    }

    @TestConfiguration
    static class QueryTestConfig {
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
