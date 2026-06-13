package io.datagov.server.metadata;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
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
class MetadataControllerTest {
    private static final String BASE_PATH = "/rest/oss/inner/modelengineservice/v1";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void snapshotRegisterCreatesAndListsFormalMetadata() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(1))
                .andExpect(jsonPath("$.updatedCount").value(0))
                .andExpect(jsonPath("$.unchangedCount").value(0))
                .andExpect(jsonPath("$.removedBySnapshotCount").value(0))
                .andExpect(jsonPath("$.items[0].assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.items[0].status").value("CREATED"));

        String metadataId = metadataId("ads_cell_profile");

        mockMvc.perform(get(BASE_PATH + "/metadata")
                        .param("keyword", "cell")
                        .param("page", "1")
                        .param("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(1)))
                .andExpect(jsonPath("$.items[0].metadataId").value(metadataId))
                .andExpect(jsonPath("$.items[0].metadataType").value("TABLE"))
                .andExpect(jsonPath("$.items[0].sourceType").value("STARROCKS"));

        mockMvc.perform(get(BASE_PATH + "/metadata/{metadataId}", metadataId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.schema[0].fieldName").value("cell_id"))
                .andExpect(jsonPath("$.binding.qualifiedName").value("default_catalog.ads.ads_cell_profile"));
    }

    @Test
    void repeatedSnapshotReturnsUnchangedWithoutIncrementingSchemaVersion() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk());
        int schemaVersion = schemaVersion("ads_cell_profile");

        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(0))
                .andExpect(jsonPath("$.updatedCount").value(0))
                .andExpect(jsonPath("$.unchangedCount").value(1))
                .andExpect(jsonPath("$.items[0].status").value("UNCHANGED"));

        assertThat(schemaVersion("ads_cell_profile")).isEqualTo(schemaVersion);
    }

    @Test
    void metadataDetailJoinsNonBlankBindingPartsWhenCatalogIsOmitted() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithItem(partialBindingItem())))
                .andExpect(status().isOk());

        String metadataId = metadataId("ads_partial_binding");
        mockMvc.perform(get(BASE_PATH + "/metadata/{metadataId}", metadataId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.binding.qualifiedName").value("ads.ads_partial_binding"));
    }

    @Test
    void repeatedSnapshotIgnoresBindingPropertiesObjectKeyOrder() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithItem(itemWithBindingProperties("""
                                {
                                  "partitions": 16,
                                  "replication": 3
                                }
                                """))))
                .andExpect(status().isOk());
        int schemaVersion = schemaVersion("ads_properties_order");

        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithItem(itemWithBindingProperties("""
                                {
                                  "replication": 3,
                                  "partitions": 16
                                }
                                """))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.createdCount").value(0))
                .andExpect(jsonPath("$.updatedCount").value(0))
                .andExpect(jsonPath("$.unchangedCount").value(1))
                .andExpect(jsonPath("$.items[0].status").value("UNCHANGED"));

        assertThat(schemaVersion("ads_properties_order")).isEqualTo(schemaVersion);
    }

    @Test
    void metadataListWithVeryLargePageReturnsEmptyItems() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk());

        mockMvc.perform(get(BASE_PATH + "/metadata")
                        .param("page", String.valueOf(Integer.MAX_VALUE))
                        .param("size", "100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items", hasSize(0)));
    }

    @Test
    void changedSnapshotUpdatesExistingMetadata() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk());

        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithItem(changedCellProfileItem())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.updatedCount").value(1))
                .andExpect(jsonPath("$.items[0].status").value("UPDATED"));

        String metadataId = metadataId("ads_cell_profile");
        mockMvc.perform(get(BASE_PATH + "/metadata/{metadataId}", metadataId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.assetName").value("ADS Cell Profile V2"))
                .andExpect(jsonPath("$.schema", hasSize(2)));
    }

    @Test
    void fullSnapshotMarksMissingScopedMetadataRemovedBySnapshot() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile", "ads_cell_quality")))
                .andExpect(status().isOk());
        String removedMetadataId = metadataId("ads_cell_quality");

        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.removedBySnapshotCount").value(1))
                .andExpect(jsonPath("$.items[?(@.assetCode == 'ads_cell_quality')]", hasSize(1)))
                .andExpect(jsonPath("$.items[?(@.assetCode == 'ads_cell_quality')].status",
                        contains("REMOVED_BY_SNAPSHOT")));

        mockMvc.perform(get(BASE_PATH + "/metadata/{metadataId}", removedMetadataId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadataId").value(removedMetadataId))
                .andExpect(jsonPath("$.assetCode").value("ads_cell_quality"))
                .andExpect(jsonPath("$.queryable").value(false));
    }

    @Test
    void snapshotRegisterReplacesDeclaredLineageForProducerScope() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithItem("""
                                %s,
                                %s
                                """.formatted(upstreamCellProfileItem(), targetCellProfileItemWithLineage(true)))))
                .andExpect(status().isOk());

        assertThat(activeLineageEdgeCount("dwd_cell_profile", "ads_cell_profile")).isEqualTo(1);
        assertThat(activeFieldLineageCount()).isEqualTo(1);

        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithItem("""
                                %s,
                                %s
                                """.formatted(upstreamCellProfileItem(), targetCellProfileItemWithLineage(false)))))
                .andExpect(status().isOk());

        assertThat(activeLineageEdgeCount("dwd_cell_profile", "ads_cell_profile")).isEqualTo(0);
        assertThat(activeFieldLineageCount()).isEqualTo(0);
    }

    @Test
    void fullSnapshotDoesNotMarkMissingOfflineScopedMetadataRemovedBySnapshot() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile", "ads_cell_quality")))
                .andExpect(status().isOk());
        jdbcTemplate.update(
                "update data_asset set lifecycle_status = 'OFFLINE' where asset_code = ?",
                "ads_cell_quality");

        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.removedBySnapshotCount").value(0));

        assertThat(lifecycleStatus("ads_cell_quality")).isEqualTo("OFFLINE");
    }

    @Test
    void patchAndDeleteMetadataByIdReuseRuntimeMutationBehavior() throws Exception {
        mockMvc.perform(post(BASE_PATH + "/metadata/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(snapshotWithAssets("ads_cell_profile")))
                .andExpect(status().isOk());
        String metadataId = metadataId("ads_cell_profile");

        mockMvc.perform(patch(BASE_PATH + "/metadata/{metadataId}", metadataId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetName": "ADS Cell Profile Runtime",
                                  "description": "Runtime metadata update"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UPDATED"))
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.assetCode").value("ads_cell_profile"));

        mockMvc.perform(delete(BASE_PATH + "/metadata/{metadataId}", metadataId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "reason": "dataset retired",
                                  "operator": "network-team"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UNREGISTERED"))
                .andExpect(jsonPath("$.metadataId").value(metadataId))
                .andExpect(jsonPath("$.assetCode").value("ads_cell_profile"));
    }

    private String snapshotWithAssets(String... assetCodes) {
        StringBuilder metadataList = new StringBuilder();
        for (int i = 0; i < assetCodes.length; i++) {
            if (i > 0) {
                metadataList.append(",\n");
            }
            metadataList.append(defaultItem(assetCodes[i]));
        }
        return snapshotWithItem(metadataList.toString());
    }

    private String snapshotWithItem(String metadataList) {
        return """
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
                    %s
                  ]
                }
                """.formatted(metadataList);
    }

    private String defaultItem(String assetCode) {
        String assetName = switch (assetCode) {
            case "ads_cell_profile" -> "ADS Cell Profile";
            case "ads_cell_quality" -> "ADS Cell Quality";
            default -> assetCode;
        };
        return """
                {
                  "assetCode": "%s",
                  "assetName": "%s",
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
                    }
                  ],
                  "binding": {
                    "sourceType": "STARROCKS",
                    "catalog": "default_catalog",
                    "database": "ads",
                    "table": "%s",
                    "queryAdapter": "starrocks"
                  }
                }
                """.formatted(assetCode, assetName, assetCode);
    }

    private String upstreamCellProfileItem() {
        return """
                {
                  "assetCode": "dwd_cell_profile",
                  "assetName": "DWD Cell Profile",
                  "metadataType": "TABLE",
                  "sourceType": "HIVE",
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
                      "fieldName": "rsrp_avg",
                      "fieldType": "double",
                      "ordinal": 2,
                      "nullable": true
                    }
                  ],
                  "binding": {
                    "sourceType": "HIVE",
                    "catalog": "hive",
                    "database": "dwd",
                    "table": "dwd_cell_profile",
                    "queryAdapter": "hive"
                  }
                }
                """;
    }

    private String targetCellProfileItemWithLineage(boolean includeUpstream) {
        String upstreams = includeUpstream ? """
                    {
                      "assetCode": "dwd_cell_profile",
                      "lineageType": "FIELD",
                      "transformType": "SQL",
                      "expression": "coverage_score = normalize(rsrp_avg)",
                      "processName": "cell-profile-aggregation",
                      "jobName": "ads-cell-profile-snapshot",
                      "fieldMappings": [
                        {
                          "sourceField": "rsrp_avg",
                          "targetField": "coverage_score",
                          "expression": "normalize(rsrp_avg)"
                        }
                      ]
                    }
                """ : "";
        return """
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
                  },
                  "lineage": {
                    "upstreams": [
                      %s
                    ],
                    "downstreams": []
                  }
                }
                """.formatted(upstreams);
    }

    private String partialBindingItem() {
        return """
                {
                  "assetCode": "ads_partial_binding",
                  "assetName": "ADS Partial Binding",
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
                    }
                  ],
                  "binding": {
                    "sourceType": "STARROCKS",
                    "database": "ads",
                    "table": "ads_partial_binding",
                    "queryAdapter": "starrocks"
                  }
                }
                """;
    }

    private String itemWithBindingProperties(String properties) {
        return """
                {
                  "assetCode": "ads_properties_order",
                  "assetName": "ADS Properties Order",
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
                    }
                  ],
                  "binding": {
                    "sourceType": "STARROCKS",
                    "catalog": "default_catalog",
                    "database": "ads",
                    "table": "ads_properties_order",
                    "queryAdapter": "starrocks",
                    "properties": %s
                  }
                }
                """.formatted(properties);
    }

    private String changedCellProfileItem() {
        return """
                {
                  "assetCode": "ads_cell_profile",
                  "assetName": "ADS Cell Profile V2",
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
                """;
    }

    private String metadataId(String assetCode) {
        return jdbcTemplate.queryForObject(
                "select asset_id from data_asset where asset_code = ?",
                String.class,
                assetCode);
    }

    private int schemaVersion(String assetCode) {
        return jdbcTemplate.queryForObject(
                "select schema_version from data_asset where asset_code = ?",
                Integer.class,
                assetCode);
    }

    private int activeLineageEdgeCount(String sourceAssetCode, String targetAssetCode) {
        return jdbcTemplate.queryForObject("""
                select count(*)
                from lineage_edge le
                join data_asset source_asset on source_asset.asset_id = le.source_asset_id
                join data_asset target_asset on target_asset.asset_id = le.target_asset_id
                where le.active = true
                  and source_asset.asset_code = ?
                  and target_asset.asset_code = ?
                """, Integer.class, sourceAssetCode, targetAssetCode);
    }

    private int activeFieldLineageCount() {
        return jdbcTemplate.queryForObject("""
                select count(*)
                from lineage_field_edge lfe
                join lineage_edge le on le.edge_id = lfe.lineage_edge_id
                where lfe.active = true
                  and le.active = true
                """, Integer.class);
    }

    private String lifecycleStatus(String assetCode) {
        return jdbcTemplate.queryForObject(
                "select lifecycle_status from data_asset where asset_code = ?",
                String.class,
                assetCode);
    }
}
