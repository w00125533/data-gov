package io.datagov.server.asset;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AssetControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Test
    void registerAndReadTableAsset() throws Exception {
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
                                      "ordinalPosition": 1,
                                      "nullable": false,
                                      "primaryKey": true
                                    },
                                    {
                                      "fieldName": "province",
                                      "fieldType": "varchar",
                                      "ordinalPosition": 2,
                                      "nullable": true
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
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.asset.queryable").value(true))
                .andExpect(jsonPath("$.asset.federatedQueryable").value(true))
                .andExpect(jsonPath("$.fields", hasSize(2)))
                .andExpect(jsonPath("$.binding.tableName").value("ads_cell_profile"));

        mockMvc.perform(get("/api/assets"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].assetCode").value("ads_cell_profile"));

        mockMvc.perform(get("/api/assets/ads_cell_profile"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.fields[0].fieldName").value("cell_id"))
                .andExpect(jsonPath("$.binding.engine").value("STARROCKS"));

        mockMvc.perform(get("/api/assets/ads_cell_profile/schema"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(2)))
                .andExpect(jsonPath("$[0].fieldName").value("cell_id"))
                .andExpect(jsonPath("$[1].fieldName").value("province"));

        mockMvc.perform(get("/api/assets/ads_cell_profile/binding"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.catalogName").value("default_catalog"))
                .andExpect(jsonPath("$.databaseName").value("ads"))
                .andExpect(jsonPath("$.tableName").value("ads_cell_profile"))
                .andExpect(jsonPath("$.active").value(true));
    }

    @Test
    void kafkaAssetCanRegisterButIsNotQueryable() throws Exception {
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "ods_ue_signal",
                                  "assetName": "ODS UE Signal",
                                  "assetType": "STREAM",
                                  "engine": "KAFKA",
                                  "lifecycleStatus": "ACTIVE",
                                  "queryable": true,
                                  "federatedQueryable": true,
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
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.assetCode").value("ods_ue_signal"))
                .andExpect(jsonPath("$.asset.queryable").value(false))
                .andExpect(jsonPath("$.asset.federatedQueryable").value(false))
                .andExpect(jsonPath("$.binding.topicName").value("ods_ue_signal"));
    }

    @Test
    void registerSameAssetCodeUpdatesExistingAsset() throws Exception {
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "dim_asset_upsert",
                                  "assetName": "Original Asset",
                                  "assetType": "TABLE",
                                  "engine": "STARROCKS",
                                  "lifecycleStatus": "DRAFT",
                                  "fields": [
                                    {
                                      "fieldName": "asset_id",
                                      "fieldType": "varchar",
                                      "ordinalPosition": 1
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.assetName").value("Original Asset"))
                .andExpect(jsonPath("$.asset.schemaVersion").value(1));

        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "dim_asset_upsert",
                                  "assetName": "Updated Asset",
                                  "assetType": "TABLE",
                                  "engine": "STARROCKS",
                                  "lifecycleStatus": "ACTIVE",
                                  "fields": [
                                    {
                                      "fieldName": "asset_id",
                                      "fieldType": "varchar",
                                      "ordinalPosition": 1
                                    },
                                    {
                                      "fieldName": "asset_name",
                                      "fieldType": "varchar",
                                      "ordinalPosition": 2
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.assetName").value("Updated Asset"))
                .andExpect(jsonPath("$.asset.schemaVersion").value(2))
                .andExpect(jsonPath("$.fields", hasSize(2)));

        mockMvc.perform(get("/api/assets"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.assetCode == 'dim_asset_upsert')]", hasSize(1)));

        mockMvc.perform(get("/api/assets/dim_asset_upsert"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.assetName").value("Updated Asset"))
                .andExpect(jsonPath("$.fields", hasSize(2)));
    }

    @Test
    void omittedFieldOrdinalsPreserveRequestOrder() throws Exception {
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "dim_request_order",
                                  "assetName": "Request Order Asset",
                                  "assetType": "TABLE",
                                  "engine": "STARROCKS",
                                  "fields": [
                                    {
                                      "fieldName": "zeta_field",
                                      "fieldType": "varchar"
                                    },
                                    {
                                      "fieldName": "alpha_field",
                                      "fieldType": "varchar"
                                    },
                                    {
                                      "fieldName": "middle_field",
                                      "fieldType": "varchar"
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.fields[0].fieldName").value("zeta_field"))
                .andExpect(jsonPath("$.fields[0].ordinalPosition").value(1))
                .andExpect(jsonPath("$.fields[1].fieldName").value("alpha_field"))
                .andExpect(jsonPath("$.fields[1].ordinalPosition").value(2))
                .andExpect(jsonPath("$.fields[2].fieldName").value("middle_field"))
                .andExpect(jsonPath("$.fields[2].ordinalPosition").value(3));

        mockMvc.perform(get("/api/assets/dim_request_order/schema"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(3)))
                .andExpect(jsonPath("$[0].fieldName").value("zeta_field"))
                .andExpect(jsonPath("$[1].fieldName").value("alpha_field"))
                .andExpect(jsonPath("$[2].fieldName").value("middle_field"));
    }

    @Test
    void unknownAssetReturns404() throws Exception {
        mockMvc.perform(get("/api/assets/missing_asset"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
    }
}
