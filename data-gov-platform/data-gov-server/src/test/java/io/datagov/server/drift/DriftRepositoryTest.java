package io.datagov.server.drift;

import io.datagov.common.enums.DriftStatus;
import io.datagov.common.enums.DriftType;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
@Transactional
class DriftRepositoryTest {
    @Autowired
    private DriftRepository driftRepository;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void upsertOpenInsertsNewRecord() {
        DriftRepository.UpsertedDriftRecord result = driftRepository.upsertOpen(
                "drift_new",
                DriftType.DECLARED_UNUSED,
                candidate("sub_new"),
                "DECLARED_UNUSED:sub_new",
                Map.of("subscriptionId", "sub_new"),
                Instant.parse("2026-02-01T00:00:00Z"));

        assertThat(result.created()).isTrue();
        assertThat(result.record().driftId()).isEqualTo("drift_new");
        assertThat(result.record().status()).isEqualTo(DriftStatus.OPEN);
        assertThat(result.record().resolvedAt()).isNull();
    }

    @Test
    void upsertOpenReopensResolvedRecordAndClearsResolvedAt() {
        jdbcTemplate.update("""
                insert into drift_record (
                    drift_id, drift_type, unique_key, evidence, status, detected_at, resolved_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                "drift_existing",
                DriftType.DECLARED_UNUSED.name(),
                "DECLARED_UNUSED:sub_existing",
                "{}",
                DriftStatus.RESOLVED.name(),
                Timestamp.from(Instant.parse("2026-01-01T00:00:00Z")),
                Timestamp.from(Instant.parse("2026-01-02T00:00:00Z")));

        DriftRepository.UpsertedDriftRecord result = driftRepository.upsertOpen(
                "drift_ignored",
                DriftType.DECLARED_UNUSED,
                candidate("sub_existing"),
                "DECLARED_UNUSED:sub_existing",
                Map.of("subscriptionId", "sub_existing", "assetCode", "ads_cell_profile"),
                Instant.parse("2026-02-01T00:00:00Z"));

        assertThat(result.created()).isFalse();
        assertThat(result.record().driftId()).isEqualTo("drift_existing");
        assertThat(result.record().status()).isEqualTo(DriftStatus.OPEN);
        assertThat(result.record().resolvedAt()).isNull();
        assertThat(result.record().detectedAt()).isEqualTo(Instant.parse("2026-02-01T00:00:00Z"));
        assertThat(result.record().evidence()).containsEntry("assetCode", "ads_cell_profile");
    }

    private DriftRepository.DriftCandidate candidate(String subscriptionId) {
        return new DriftRepository.DriftCandidate(
                null,
                null,
                "ads_cell_profile",
                null,
                "rno-dashboard",
                null,
                Instant.parse("2026-01-01T00:00:00Z"),
                0,
                null,
                null);
    }
}
