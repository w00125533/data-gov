package io.datagov.server.metadata;

import io.datagov.common.dto.MetadataDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LifecycleStatus;
import io.datagov.common.enums.MetadataProducerType;
import io.datagov.common.enums.MetadataSyncItemStatus;
import io.datagov.common.enums.MetadataSyncMode;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
class MetadataSchemaMigrationTest {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void metadataSnapshotColumnsAndDtosAreAvailable() {
        Integer columnCount = jdbcTemplate.queryForObject("""
                select count(*)
                from information_schema.columns
                where lower(table_name) = 'data_asset'
                  and lower(column_name) in (
                      'producer_service_name',
                      'producer_service_type',
                      'producer_environment',
                      'declaration_hash',
                      'last_synced_at',
                      'unregistered_at'
                  )
                """, Integer.class);

        MetadataDtos.MetadataSnapshotRegisterRequest request =
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
                                "wireless-rno",
                                "network-team",
                                "Cell profile table",
                                true,
                                true,
                                List.of(new MetadataDtos.MetadataFieldRequest(
                                        "cell_id",
                                        "varchar",
                                        1,
                                        false,
                                        false,
                                        true,
                                        false,
                                        "Cell id",
                                        null)),
                                new MetadataDtos.MetadataBindingRequest(
                                        AssetEngine.STARROCKS,
                                        "default_catalog",
                                        "ads",
                                        null,
                                        "ads_cell_profile",
                                        null,
                                        null,
                                        null,
                                        null,
                                        "starrocks",
                                        Map.of()),
                                null)));

        MetadataDtos.MetadataSyncResponse response = new MetadataDtos.MetadataSyncResponse(
                new MetadataDtos.MetadataSyncScope("rno-profile-service", "prod"),
                1,
                0,
                0,
                0,
                List.of(new MetadataDtos.MetadataSyncItemResponse(
                        "asset_1",
                        "ads_cell_profile",
                        MetadataSyncItemStatus.CREATED)),
                Instant.parse("2026-06-13T00:00:00Z"));

        assertThat(columnCount).isEqualTo(6);
        assertThat(request.producer().serviceName()).isEqualTo("rno-profile-service");
        assertThat(response.items().get(0).status()).isEqualTo(MetadataSyncItemStatus.CREATED);
        assertThat(LifecycleStatus.valueOf("REMOVED_BY_SNAPSHOT")).isEqualTo(LifecycleStatus.REMOVED_BY_SNAPSHOT);
    }
}
