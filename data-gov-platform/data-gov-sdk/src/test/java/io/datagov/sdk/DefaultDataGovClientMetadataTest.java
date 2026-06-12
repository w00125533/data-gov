package io.datagov.sdk;

import io.datagov.common.dto.MetadataDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.MetadataProducerType;
import io.datagov.common.enums.MetadataSyncItemStatus;
import io.datagov.common.enums.MetadataSyncMode;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class DefaultDataGovClientMetadataTest {
    @Test
    void registerMetadataSnapshotUsesFormalMetadataPath() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://data-gov");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        DefaultDataGovClient client = new DefaultDataGovClient(builder.build());

        server.expect(once(), requestTo("http://data-gov/rest/oss/inner/modelengineservice/v1/metadata/register"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withSuccess("""
                        {
                          "syncScope": {"serviceName": "rno-profile-service", "environment": "prod"},
                          "createdCount": 1,
                          "updatedCount": 0,
                          "unchangedCount": 0,
                          "removedBySnapshotCount": 0,
                          "items": [
                            {"metadataId": "asset_1", "assetCode": "ads_cell_profile", "status": "CREATED"}
                          ],
                          "syncedAt": "2026-06-13T00:00:00Z"
                        }
                        """, org.springframework.http.MediaType.APPLICATION_JSON));

        MetadataDtos.MetadataSyncResponse response = client.registerMetadataSnapshot(
                new MetadataDtos.MetadataSnapshotRegisterRequest(
                        new MetadataDtos.ProducerRequest(
                                "rno-profile-service",
                                MetadataProducerType.MICROSERVICE,
                                "network-team",
                                "prod",
                                "pod-1"),
                        MetadataSyncMode.FULL,
                        List.of(new MetadataDtos.MetadataItemRequest(
                                "ads_cell_profile",
                                "ADS Cell Profile",
                                AssetType.TABLE,
                                AssetEngine.STARROCKS,
                                "wireless",
                                "network-team",
                                null,
                                true,
                                true,
                                List.of(),
                                null,
                                null))));

        assertThat(response.createdCount()).isEqualTo(1);
        assertThat(response.items().get(0).status()).isEqualTo(MetadataSyncItemStatus.CREATED);
        assertThat(response.syncedAt()).isEqualTo(Instant.parse("2026-06-13T00:00:00Z"));
        server.verify();
    }
}
