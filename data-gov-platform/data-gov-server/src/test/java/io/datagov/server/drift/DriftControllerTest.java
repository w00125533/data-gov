package io.datagov.server.drift;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.sql.Timestamp;
import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.notNullValue;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class DriftControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void analyzeCreatesDeclaredUnusedDriftForActiveSubscriptionWithoutRuntimeUsage() throws Exception {
        registerAsset("ads_cell_profile");
        String subscriptionId = createSubscription("ads_cell_profile", "rno-dashboard");
        Instant oldRegistration = Instant.now().minus(45, ChronoUnit.DAYS);
        jdbcTemplate.update("""
                update subscription
                set last_registered_at = ?, last_runtime_seen_at = null
                where subscription_id = ?
                """, Timestamp.from(oldRegistration), subscriptionId);

        mockMvc.perform(post("/api/drift/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "unusedAfterDays": 30,
                                  "staleAfterDays": 90,
                                  "usageLookbackDays": 7
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1))
                .andExpect(jsonPath("$.refreshedCount").value(0))
                .andExpect(jsonPath("$.records", hasSize(1)))
                .andExpect(jsonPath("$.records[0].driftType").value("DECLARED_UNUSED"))
                .andExpect(jsonPath("$.records[0].status").value("OPEN"))
                .andExpect(jsonPath("$.records[0].assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.records[0].consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.records[0].subscriptionId").value(subscriptionId))
                .andExpect(jsonPath("$.records[0].evidence.subscriptionId").value(subscriptionId))
                .andExpect(jsonPath("$.records[0].evidence.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.records[0].evidence.consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.records[0].evidence.lastRuntimeSeenAt", nullValue()))
                .andExpect(jsonPath("$.records[0].evidence.unusedCutoff", notNullValue()));
    }

    @Test
    void analyzeCreatesUndeclaredUsageDriftForSuccessfulQueryWithoutActiveSubscription() throws Exception {
        registerAsset("ads_cell_profile");
        String consumerId = insertConsumer("consumer_undeclared", "adhoc-analyst");
        insertSuccessfulQuery("query_undeclared", assetId("ads_cell_profile"), consumerId, null, Instant.now());

        mockMvc.perform(post("/api/drift/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "unusedAfterDays": 30,
                                  "staleAfterDays": 90,
                                  "usageLookbackDays": 7
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1))
                .andExpect(jsonPath("$.refreshedCount").value(0))
                .andExpect(jsonPath("$.records", hasSize(1)))
                .andExpect(jsonPath("$.records[0].driftType").value("UNDECLARED_USAGE"))
                .andExpect(jsonPath("$.records[0].status").value("OPEN"))
                .andExpect(jsonPath("$.records[0].assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.records[0].consumerName").value("adhoc-analyst"))
                .andExpect(jsonPath("$.records[0].subscriptionId", nullValue()))
                .andExpect(jsonPath("$.records[0].evidence.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.records[0].evidence.consumerName").value("adhoc-analyst"))
                .andExpect(jsonPath("$.records[0].evidence.queryCount").value(1))
                .andExpect(jsonPath("$.records[0].evidence.firstSeenAt", notNullValue()))
                .andExpect(jsonPath("$.records[0].evidence.lastSeenAt", notNullValue()))
                .andExpect(jsonPath("$.records[0].evidence.usageSince", notNullValue()));
    }

    @Test
    void analyzeCreatesStaleDeclarationDriftForActiveSubscriptionWithStaleRegistration() throws Exception {
        registerAsset("ads_cell_profile");
        String subscriptionId = createSubscription("ads_cell_profile", "rno-dashboard");
        Instant now = Instant.now();
        Instant staleRegistration = now.minus(120, ChronoUnit.DAYS);
        jdbcTemplate.update("""
                update subscription
                set last_registered_at = ?, last_runtime_seen_at = ?
                where subscription_id = ?
                """, Timestamp.from(staleRegistration), Timestamp.from(now), subscriptionId);

        mockMvc.perform(post("/api/drift/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "unusedAfterDays": 30,
                                  "staleAfterDays": 90,
                                  "usageLookbackDays": 7
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1))
                .andExpect(jsonPath("$.refreshedCount").value(0))
                .andExpect(jsonPath("$.records", hasSize(1)))
                .andExpect(jsonPath("$.records[0].driftType").value("STALE_DECLARATION"))
                .andExpect(jsonPath("$.records[0].status").value("OPEN"))
                .andExpect(jsonPath("$.records[0].assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.records[0].consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.records[0].subscriptionId").value(subscriptionId))
                .andExpect(jsonPath("$.records[0].evidence.subscriptionId").value(subscriptionId))
                .andExpect(jsonPath("$.records[0].evidence.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.records[0].evidence.consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.records[0].evidence.lastRegisteredAt", notNullValue()))
                .andExpect(jsonPath("$.records[0].evidence.staleCutoff", notNullValue()));
    }

    @Test
    void repeatedAnalyzeRefreshesExistingOpenDriftAndListReturnsSingleOrderedRecord() throws Exception {
        registerAsset("ads_cell_profile");
        String subscriptionId = createSubscription("ads_cell_profile", "rno-dashboard");
        jdbcTemplate.update("""
                update subscription
                set last_registered_at = ?, last_runtime_seen_at = null
                where subscription_id = ?
                """, Timestamp.from(Instant.now().minus(45, ChronoUnit.DAYS)), subscriptionId);

        mockMvc.perform(post("/api/drift/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "unusedAfterDays": 30,
                                  "staleAfterDays": 90,
                                  "usageLookbackDays": 7
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1))
                .andExpect(jsonPath("$.refreshedCount").value(0))
                .andExpect(jsonPath("$.records", hasSize(1)))
                .andExpect(jsonPath("$.records[0].driftType").value("DECLARED_UNUSED"))
                .andExpect(jsonPath("$.records[0].subscriptionId").value(subscriptionId));

        mockMvc.perform(post("/api/drift/analyze")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "unusedAfterDays": 30,
                                  "staleAfterDays": 90,
                                  "usageLookbackDays": 7
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(0))
                .andExpect(jsonPath("$.refreshedCount").value(1))
                .andExpect(jsonPath("$.records", hasSize(1)))
                .andExpect(jsonPath("$.records[0].driftType").value("DECLARED_UNUSED"))
                .andExpect(jsonPath("$.records[0].status").value("OPEN"))
                .andExpect(jsonPath("$.records[0].assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.records[0].consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.records[0].subscriptionId").value(subscriptionId));

        mockMvc.perform(get("/api/drift"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].driftType").value("DECLARED_UNUSED"))
                .andExpect(jsonPath("$[0].status").value("OPEN"))
                .andExpect(jsonPath("$[0].assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$[0].consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$[0].subscriptionId").value(subscriptionId));
    }

    private void registerAsset(String assetCode) throws Exception {
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
                                      "ordinalPosition": 1
                                    }
                                  ],
                                  "physicalBinding": {
                                    "engine": "STARROCKS",
                                    "catalogName": "default_catalog",
                                    "databaseName": "ads",
                                    "tableName": "%s",
                                    "queryAdapter": "starrocks"
                                  }
                                }
                                """.formatted(assetCode, assetCode, assetCode)))
                .andExpect(status().isOk());
    }

    private String createSubscription(String assetCode, String consumerName) throws Exception {
        String response = mockMvc.perform(post("/api/assets/{assetCode}/subscriptions", assetCode)
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
                                    "purpose": "dashboard display",
                                    "fields": ["cell_id"],
                                    "notifyOn": ["SCHEMA_CHANGE"]
                                  }
                                }
                                """.formatted(consumerName, assetCode)))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();
        return com.jayway.jsonpath.JsonPath.read(response, "$.subscriptionId");
    }

    private String assetId(String assetCode) {
        return jdbcTemplate.queryForObject(
                "select asset_id from data_asset where asset_code = ?",
                String.class,
                assetCode);
    }

    private String insertConsumer(String consumerId, String consumerName) {
        jdbcTemplate.update("""
                insert into consumer (
                    consumer_id, consumer_type, consumer_name, owner, environment, created_at, updated_at
                ) values (?, 'MICROSERVICE', ?, 'analytics-team', 'prod', current_timestamp, current_timestamp)
                """, consumerId, consumerName);
        return consumerId;
    }

    private void insertSuccessfulQuery(
            String queryId,
            String assetId,
            String consumerId,
            String subscriptionId,
            Instant createdAt
    ) {
        jdbcTemplate.update("""
                insert into query_record (
                    query_id, request_type, asset_id, subscription_id, consumer_id, referenced_asset_codes,
                    selected_fields, filter_json, sql_text, status, row_count, elapsed_ms, created_at
                ) values (?, 'PRODUCT_API', ?, ?, ?, ?, ?, '{}', ?, 'SUCCESS', 1, 12, ?)
                """,
                queryId,
                assetId,
                subscriptionId,
                consumerId,
                "[\"ads_cell_profile\"]",
                "[\"cell_id\"]",
                "select cell_id from ads_cell_profile",
                Timestamp.from(createdAt));
    }
}
