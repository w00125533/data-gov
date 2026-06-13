package io.datagov.common.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.common.enums.UsageMode;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FormalSubscriptionDtosContractTest {
    private final ObjectMapper objectMapper = new ObjectMapper()
            .registerModule(new JavaTimeModule());

    @Test
    void formalCreateSubscriptionRequestDeserializesFlatBody() throws Exception {
        String body = """
                {
                  "consumer": {
                    "consumerName": "rno-dashboard",
                    "consumerType": "MICROSERVICE"
                  },
                  "usageMode": "API_QUERY",
                  "purpose": "read cell profile",
                  "fields": ["cell_id", "coverage_score"],
                  "notifyOn": ["SCHEMA_CHANGE"],
                  "notificationStrategy": {
                    "delivery": "KAFKA",
                    "sdkCallback": true,
                    "consumerGroup": "rno-dashboard"
                  }
                }
                """;

        FormalSubscriptionDtos.FormalCreateSubscriptionRequest request = objectMapper.readValue(
                body,
                FormalSubscriptionDtos.FormalCreateSubscriptionRequest.class
        );

        assertEquals("rno-dashboard", request.consumer().consumerName());
        assertEquals(ConsumerType.MICROSERVICE, request.consumer().consumerType());
        assertEquals(UsageMode.API_QUERY, request.usageMode());
        assertEquals(List.of("cell_id", "coverage_score"), request.fields());
        assertEquals(List.of(AssetEventType.SCHEMA_CHANGE), request.notifyOn());
        assertEquals("KAFKA", request.notificationStrategy().delivery());
        assertTrue(request.notificationStrategy().sdkCallback());
    }

    @Test
    void formalSubscriptionResponseSerializesMetadataIdAndFields() throws Exception {
        FormalSubscriptionDtos.FormalSubscriptionResponse response =
                new FormalSubscriptionDtos.FormalSubscriptionResponse(
                        "sub_1",
                        "meta_1",
                        "ads_cell_profile",
                        "consumer_1",
                        UsageMode.API_QUERY,
                        SubscriptionStatus.ACTIVE,
                        List.of("cell_id"),
                        List.of(AssetEventType.SCHEMA_CHANGE),
                        Instant.parse("2026-06-11T00:00:00Z")
                );

        String json = objectMapper.writeValueAsString(response);

        assertTrue(json.contains("\"metadataId\":\"meta_1\""));
        assertTrue(json.contains("\"fields\":[\"cell_id\"]"));
        assertTrue(json.contains("\"status\":\"ACTIVE\""));
    }

    @Test
    void formalCancellationStatusesAreAvailable() {
        assertEquals(SubscriptionStatus.CANCELLED, SubscriptionStatus.valueOf("CANCELLED"));
        assertEquals(SubscriptionStatus.REMOVED_BY_SNAPSHOT, SubscriptionStatus.valueOf("REMOVED_BY_SNAPSHOT"));
    }
}
