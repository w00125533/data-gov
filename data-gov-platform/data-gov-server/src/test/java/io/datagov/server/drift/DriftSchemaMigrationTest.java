package io.datagov.server.drift;

import io.datagov.common.dto.DriftDtos;
import io.datagov.common.enums.DriftStatus;
import io.datagov.common.enums.DriftType;
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
class DriftSchemaMigrationTest {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void driftTableAndDtosAreAvailable() {
        Integer tableCount = jdbcTemplate.queryForObject(
                "select count(*) from information_schema.tables where lower(table_name) = 'drift_record'",
                Integer.class);

        DriftDtos.DriftRecordResponse record = new DriftDtos.DriftRecordResponse(
                "drift_1",
                DriftType.DECLARED_UNUSED,
                DriftStatus.OPEN,
                "asset_1",
                "ads_cell_profile",
                "consumer_1",
                "rno-dashboard",
                "sub_1",
                Map.of("subscriptionId", "sub_1"),
                Instant.parse("2026-06-12T00:00:00Z"),
                null);
        DriftDtos.DriftAnalysisResponse response = new DriftDtos.DriftAnalysisResponse(
                1,
                0,
                List.of(record));

        assertThat(tableCount).isEqualTo(1);
        assertThat(response.createdCount()).isEqualTo(1);
        assertThat(response.records()).hasSize(1);
        assertThat(response.records().get(0).driftType()).isEqualTo(DriftType.DECLARED_UNUSED);
    }
}
