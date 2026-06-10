package io.datagov.server.lineage;

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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class LineageControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void createsLineageEdgeAndQueriesDownstreamGraph() throws Exception {
        registerTableAsset("ods_ue_signal", "KAFKA");
        registerTableAsset("dwd_session_qos", "HIVE");
        registerTableAsset("ads_cell_profile", "STARROCKS");

        mockMvc.perform(post("/api/lineage/edges")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sourceAssetCode": "ods_ue_signal",
                                  "targetAssetCode": "dwd_session_qos",
                                  "relationType": "PRODUCES",
                                  "producer": "flink",
                                  "processName": "ue-signal-clean",
                                  "jobName": "ue-signal-clean-job",
                                  "description": "ODS stream produces DWD session QoS"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.source.assetCode").value("ods_ue_signal"))
                .andExpect(jsonPath("$.target.assetCode").value("dwd_session_qos"))
                .andExpect(jsonPath("$.relationType").value("PRODUCES"));

        mockMvc.perform(post("/api/lineage/edges")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sourceAssetCode": "dwd_session_qos",
                                  "targetAssetCode": "ads_cell_profile",
                                  "relationType": "DERIVES"
                                }
                                """))
                .andExpect(status().isOk());

        mockMvc.perform(get("/api/assets/ods_ue_signal/lineage")
                        .param("direction", "down")
                        .param("depth", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.root.assetCode").value("ods_ue_signal"))
                .andExpect(jsonPath("$.direction").value("DOWN"))
                .andExpect(jsonPath("$.nodes", hasSize(3)))
                .andExpect(jsonPath("$.edges", hasSize(2)));
    }

    @Test
    void upstreamLineageHonorsDepthLimit() throws Exception {
        registerTableAsset("ods_ue_signal", "KAFKA");
        registerTableAsset("dwd_session_qos", "HIVE");
        registerTableAsset("ads_cell_profile", "STARROCKS");
        createEdge("ods_ue_signal", "dwd_session_qos", "PRODUCES");
        createEdge("dwd_session_qos", "ads_cell_profile", "DERIVES");

        mockMvc.perform(get("/api/assets/ads_cell_profile/lineage")
                        .param("direction", "up")
                        .param("depth", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nodes", hasSize(2)))
                .andExpect(jsonPath("$.edges", hasSize(1)))
                .andExpect(jsonPath("$.edges[0].source.assetCode").value("dwd_session_qos"));
    }

    @Test
    void lineageTraversalDoesNotLoopOnCycles() throws Exception {
        registerTableAsset("asset_a", "STARROCKS");
        registerTableAsset("asset_b", "STARROCKS");
        createEdge("asset_a", "asset_b", "DEPENDS_ON");
        createEdge("asset_b", "asset_a", "DEPENDS_ON");

        mockMvc.perform(get("/api/assets/asset_a/lineage")
                        .param("direction", "down")
                        .param("depth", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nodes", hasSize(2)))
                .andExpect(jsonPath("$.edges", hasSize(2)));
    }

    @Test
    void lineageExcludesInactiveEdges() throws Exception {
        registerTableAsset("asset_root", "STARROCKS");
        registerTableAsset("asset_downstream", "STARROCKS");
        createEdge("asset_root", "asset_downstream", "DERIVES");
        jdbcTemplate.update("""
                update lineage_edge
                set active = false
                where source_asset_id = ? and target_asset_id = ?
                """, assetId("asset_root"), assetId("asset_downstream"));

        mockMvc.perform(get("/api/assets/asset_root/lineage")
                        .param("direction", "down")
                        .param("depth", "5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nodes", hasSize(1)))
                .andExpect(jsonPath("$.nodes[0].assetCode").value("asset_root"))
                .andExpect(jsonPath("$.edges", hasSize(0)));
    }

    @Test
    void selfLineageEdgeReturnsBadRequest() throws Exception {
        registerTableAsset("ads_cell_profile", "STARROCKS");

        mockMvc.perform(post("/api/lineage/edges")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sourceAssetCode": "ads_cell_profile",
                                  "targetAssetCode": "ads_cell_profile",
                                  "relationType": "DERIVES"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("INVALID_LINEAGE_EDGE"));
    }

    @Test
    void impactIncludesDownstreamSubscriptionsAndRecentQueries() throws Exception {
        registerTableAsset("ods_ue_signal", "KAFKA");
        registerTableAsset("dwd_session_qos", "HIVE");
        registerTableAsset("ads_cell_profile", "STARROCKS");
        registerTableAsset("unrelated_asset", "STARROCKS");
        createEdge("ods_ue_signal", "dwd_session_qos", "PRODUCES");
        createEdge("dwd_session_qos", "ads_cell_profile", "DERIVES");
        createSubscription("ads_cell_profile", "rno-dashboard");

        insertQueryRecord("qry_by_asset_id", assetId("dwd_session_qos"), "[]", Instant.now().minus(1, ChronoUnit.DAYS));
        insertQueryRecord("qry_by_referenced_code", assetId("unrelated_asset"), "[\"ads_cell_profile\"]",
                Instant.now().minus(2, ChronoUnit.DAYS));
        insertQueryRecord("qry_unrelated", assetId("unrelated_asset"), "[\"unrelated_asset\"]",
                Instant.now().minus(3, ChronoUnit.DAYS));

        mockMvc.perform(get("/api/assets/ods_ue_signal/impact")
                        .param("depth", "5")
                        .param("recentDays", "30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.root.assetCode").value("ods_ue_signal"))
                .andExpect(jsonPath("$.depth").value(5))
                .andExpect(jsonPath("$.downstreamLineage.direction").value("DOWN"))
                .andExpect(jsonPath("$.downstreamLineage.nodes", hasSize(3)))
                .andExpect(jsonPath("$.subscriptions", hasSize(1)))
                .andExpect(jsonPath("$.subscriptions[0].assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.subscriptions[0].consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.subscriptions[0].declaredFields[0]").value("cell_id"))
                .andExpect(jsonPath("$.recentQueries", hasSize(2)))
                .andExpect(jsonPath("$.recentQueries[0].queryId").value("qry_by_asset_id"))
                .andExpect(jsonPath("$.recentQueries[1].queryId").value("qry_by_referenced_code"))
                .andExpect(jsonPath("$.recentQueries[1].referencedAssetCodes[0]").value("ads_cell_profile"));
    }

    @Test
    void impactExcludesInactiveSubscriptions() throws Exception {
        registerTableAsset("ads_cell_profile", "STARROCKS");
        createSubscription("ads_cell_profile", "rno-dashboard");
        jdbcTemplate.update(
                "update subscription set status = 'INACTIVE' where asset_id = ?",
                assetId("ads_cell_profile"));

        mockMvc.perform(get("/api/assets/ads_cell_profile/impact"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.subscriptions", hasSize(0)));
    }

    @Test
    void impactDepthClampIncludesOneHopWhenDepthIsZero() throws Exception {
        registerTableAsset("asset_root", "STARROCKS");
        registerTableAsset("asset_downstream", "STARROCKS");
        createEdge("asset_root", "asset_downstream", "DERIVES");

        mockMvc.perform(get("/api/assets/asset_root/impact")
                        .param("depth", "0"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.depth").value(1))
                .andExpect(jsonPath("$.downstreamLineage.depth").value(1))
                .andExpect(jsonPath("$.downstreamLineage.nodes", hasSize(2)))
                .andExpect(jsonPath("$.downstreamLineage.edges", hasSize(1)));
    }

    @Test
    void impactRecentDaysFiltersOldQueries() throws Exception {
        registerTableAsset("ods_ue_signal", "KAFKA");
        registerTableAsset("dwd_session_qos", "HIVE");
        createEdge("ods_ue_signal", "dwd_session_qos", "PRODUCES");

        insertQueryRecord("qry_recent", assetId("dwd_session_qos"), "[]", Instant.now().minus(2, ChronoUnit.DAYS));
        insertQueryRecord("qry_old", assetId("dwd_session_qos"), "[]", Instant.now().minus(40, ChronoUnit.DAYS));

        mockMvc.perform(get("/api/assets/ods_ue_signal/impact")
                        .param("recentDays", "7"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.recentQueries", hasSize(1)))
                .andExpect(jsonPath("$.recentQueries[0].queryId").value("qry_recent"));
    }

    @Test
    void impactRecentDaysClampUsesMinimumOneDay() throws Exception {
        registerTableAsset("asset_root", "STARROCKS");
        insertQueryRecord("qry_two_days_old", assetId("asset_root"), "[]",
                Instant.now().minus(2, ChronoUnit.DAYS));

        mockMvc.perform(get("/api/assets/asset_root/impact")
                        .param("recentDays", "0"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.recentQueries", hasSize(0)));
    }

    @Test
    void impactRecentQueriesLimitedToNewestOneHundred() throws Exception {
        registerTableAsset("asset_root", "STARROCKS");
        String assetId = assetId("asset_root");
        Instant base = Instant.now().minus(2, ChronoUnit.HOURS);
        for (int i = 0; i <= 100; i++) {
            insertQueryRecord("qry_limit_%03d".formatted(i), assetId, "[]",
                    base.plus(i, ChronoUnit.SECONDS));
        }

        mockMvc.perform(get("/api/assets/asset_root/impact")
                        .param("recentDays", "30"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.recentQueries", hasSize(100)))
                .andExpect(jsonPath("$.recentQueries[0].queryId").value("qry_limit_100"))
                .andExpect(jsonPath("$.recentQueries[?(@.queryId == 'qry_limit_000')]", hasSize(0)));
    }

    @Test
    void impactReferencedAssetCodeEscapesLikeWildcards() throws Exception {
        registerTableAsset("asset_a", "STARROCKS");
        registerTableAsset("unrelated_asset", "STARROCKS");

        insertQueryRecord("qry_false_wildcard_match", assetId("unrelated_asset"), "[\"assetXa\"]",
                Instant.now().minus(1, ChronoUnit.DAYS));

        mockMvc.perform(get("/api/assets/asset_a/impact"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.recentQueries", hasSize(0)));
    }

    private void registerTableAsset(String assetCode, String engine) throws Exception {
        String assetType = "KAFKA".equals(engine) ? "STREAM" : "TABLE";
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "%s",
                                  "assetName": "%s",
                                  "assetType": "%s",
                                  "engine": "%s",
                                  "lifecycleStatus": "ACTIVE"
                                }
                                """.formatted(assetCode, assetCode, assetType, engine)))
                .andExpect(status().isOk());
    }

    private void createEdge(String sourceAssetCode, String targetAssetCode, String relationType) throws Exception {
        mockMvc.perform(post("/api/lineage/edges")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sourceAssetCode": "%s",
                                  "targetAssetCode": "%s",
                                  "relationType": "%s"
                                }
                """.formatted(sourceAssetCode, targetAssetCode, relationType)))
                .andExpect(status().isOk());
    }

    private void createSubscription(String assetCode, String consumerName) throws Exception {
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
                                    "fields": ["cell_id"]
                                  }
                                }
                                """.formatted(consumerName, assetCode)))
                .andExpect(status().isOk());
    }

    private String assetId(String assetCode) {
        return jdbcTemplate.queryForObject(
                "select asset_id from data_asset where asset_code = ?",
                String.class,
                assetCode);
    }

    private void insertQueryRecord(String queryId, String assetId, String referencedAssetCodes, Instant createdAt) {
        jdbcTemplate.update("""
                insert into query_record (
                    query_id, request_type, asset_id, referenced_asset_codes, selected_fields, filter_json,
                    status, created_at
                ) values (?, 'PRODUCT_API', ?, ?, '[]', '{}', 'SUCCESS', ?)
                """, queryId, assetId, referencedAssetCodes, Timestamp.from(createdAt));
    }
}
