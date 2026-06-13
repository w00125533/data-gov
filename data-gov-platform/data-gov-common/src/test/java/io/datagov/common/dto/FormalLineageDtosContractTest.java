package io.datagov.common.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.enums.LineageDirection;
import io.datagov.common.enums.LineageTransformType;
import io.datagov.common.enums.LineageType;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FormalLineageDtosContractTest {
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void metadataLineageEdgeRequestDeserializesFormalLineageBody() throws Exception {
        String body = """
                {
                  "assetCode": "dwd_cell_profile",
                  "lineageType": "FIELD",
                  "transformType": "SQL",
                  "expression": "select cell_id, coverage_score from ods_cell",
                  "processName": "cell-profile-etl",
                  "jobName": "daily-cell-profile",
                  "fieldMappings": [
                    {
                      "sourceField": "cell_id",
                      "targetField": "cell_id",
                      "expression": "cell_id"
                    }
                  ]
                }
                """;

        MetadataDtos.MetadataLineageEdgeRequest request = objectMapper.readValue(
                body,
                MetadataDtos.MetadataLineageEdgeRequest.class
        );

        assertEquals("dwd_cell_profile", request.assetCode());
        assertEquals(LineageType.FIELD, request.lineageType());
        assertEquals(LineageTransformType.SQL, request.transformType());
        assertEquals("select cell_id, coverage_score from ods_cell", request.expression());
        assertEquals("cell-profile-etl", request.processName());
        assertEquals("daily-cell-profile", request.jobName());
        assertEquals(1, request.fieldMappings().size());
        assertEquals("cell_id", request.fieldMappings().get(0).sourceField());
        assertEquals("cell_id", request.fieldMappings().get(0).targetField());
        assertEquals("cell_id", request.fieldMappings().get(0).expression());
    }

    @Test
    void formalLineageResponseSerializesMetadataIdTargetFieldAndLineageType() throws Exception {
        FormalLineageDtos.FormalLineageResponse response =
                new FormalLineageDtos.FormalLineageResponse(
                        "meta_1",
                        LineageDirection.DOWN,
                        2,
                        List.of(new FormalLineageDtos.FormalLineageNode(
                                "meta_1",
                                "ods_cell",
                                "ODS Cell"
                        )),
                        List.of(),
                        List.of(new FormalLineageDtos.FormalFieldLineageEdge(
                                "meta_1",
                                "ods_cell",
                                "cell_id",
                                "meta_2",
                                "dwd_cell_profile",
                                "target_cell_id",
                                LineageType.FIELD,
                                LineageDirection.DOWN,
                                "cell_id"
                        ))
                );

        String json = objectMapper.writeValueAsString(response);

        assertTrue(json.contains("\"metadataId\":\"meta_1\""));
        assertTrue(json.contains("\"sourceMetadataId\":\"meta_1\""));
        assertTrue(json.contains("\"targetField\":\"target_cell_id\""));
        assertTrue(json.contains("\"lineageType\":\"FIELD\""));
    }
}
