package io.datagov.server.drift;

import io.datagov.common.dto.DriftDtos;
import io.datagov.common.enums.DriftStatus;
import io.datagov.common.enums.DriftType;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest
@ActiveProfiles("test")
class DriftSchemaMigrationTest {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void driftEnumsExposeStableContract() {
        assertThat(DriftType.values()).containsExactly(
                DriftType.DECLARED_UNUSED,
                DriftType.UNDECLARED_USAGE,
                DriftType.STALE_DECLARATION);
        assertThat(DriftStatus.values()).containsExactly(
                DriftStatus.OPEN,
                DriftStatus.IGNORED,
                DriftStatus.RESOLVED);
    }

    @Test
    void driftDtosExposeExpectedFields() {
        DriftDtos.AnalyzeDriftRequest request = new DriftDtos.AnalyzeDriftRequest(
                30,
                90,
                7);
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
        assertThat(request.unusedAfterDays()).isEqualTo(30);
        assertThat(request.staleAfterDays()).isEqualTo(90);
        assertThat(request.usageLookbackDays()).isEqualTo(7);
        assertThat(response.createdCount()).isEqualTo(1);
        assertThat(response.refreshedCount()).isZero();
        assertThat(response.records()).hasSize(1);
        assertThat(response.records().get(0).driftType()).isEqualTo(DriftType.DECLARED_UNUSED);
        assertThat(response.records().get(0).status()).isEqualTo(DriftStatus.OPEN);
    }

    @Test
    void driftRecordUniqueKeyEnforcesIdempotency() {
        insertDriftRecord("drift_unique_1", null, null, null, "duplicate_unique_key");

        assertThatThrownBy(() -> insertDriftRecord("drift_unique_2", null, null, null, "duplicate_unique_key"))
                .isInstanceOf(DuplicateKeyException.class);
    }

    @Test
    void driftRecordReferencesAreSetNullWhenParentsAreDeleted() {
        insertFixture("asset_null", "asset_null_code", "consumer_null", "consumer-null", "sub_null");
        insertDriftRecord("drift_asset_null", "asset_null", "consumer_null", "sub_null", "asset_null_key");
        jdbcTemplate.update("delete from data_asset where asset_id = ?", "asset_null");
        assertThat(driftReferences("drift_asset_null").get("asset_id")).isNull();

        insertFixture("asset_consumer_null", "asset_consumer_null_code", "consumer_parent_null", "consumer-parent-null",
                "sub_consumer_null");
        insertDriftRecord("drift_consumer_null", "asset_consumer_null", "consumer_parent_null", "sub_consumer_null",
                "consumer_null_key");
        jdbcTemplate.update("delete from consumer where consumer_id = ?", "consumer_parent_null");
        assertThat(driftReferences("drift_consumer_null").get("consumer_id")).isNull();

        insertFixture("asset_sub_null", "asset_sub_null_code", "consumer_sub_null", "consumer-sub-null",
                "sub_parent_null");
        insertDriftRecord("drift_sub_null", "asset_sub_null", "consumer_sub_null", "sub_parent_null", "sub_null_key");
        jdbcTemplate.update("delete from subscription where subscription_id = ?", "sub_parent_null");
        assertThat(driftReferences("drift_sub_null").get("subscription_id")).isNull();
    }

    private void insertFixture(String assetId, String assetCode, String consumerId, String consumerName,
            String subscriptionId) {
        insertAsset(assetId, assetCode);
        insertConsumer(consumerId, consumerName);
        insertSubscription(subscriptionId, assetId, consumerId);
    }

    private void insertAsset(String assetId, String assetCode) {
        jdbcTemplate.update("""
                insert into data_asset (
                    asset_id, asset_code, asset_name, asset_type, engine, lifecycle_status, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, current_timestamp, current_timestamp)
                """,
                assetId,
                assetCode,
                assetCode,
                "TABLE",
                "HIVE",
                "ACTIVE");
    }

    private void insertConsumer(String consumerId, String consumerName) {
        jdbcTemplate.update("""
                insert into consumer (
                    consumer_id, consumer_type, consumer_name, created_at, updated_at
                ) values (?, ?, ?, current_timestamp, current_timestamp)
                """,
                consumerId,
                "APPLICATION",
                consumerName);
    }

    private void insertSubscription(String subscriptionId, String assetId, String consumerId) {
        jdbcTemplate.update("""
                insert into subscription (
                    subscription_id, asset_id, consumer_id, usage_mode, source_type, status, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, current_timestamp, current_timestamp)
                """,
                subscriptionId,
                assetId,
                consumerId,
                "READ",
                "DECLARED",
                "ACTIVE");
    }

    private void insertDriftRecord(String driftId, String assetId, String consumerId, String subscriptionId,
            String uniqueKey) {
        jdbcTemplate.update("""
                insert into drift_record (
                    drift_id, drift_type, asset_id, consumer_id, subscription_id, unique_key, evidence, status, detected_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
                """,
                driftId,
                DriftType.DECLARED_UNUSED.name(),
                assetId,
                consumerId,
                subscriptionId,
                uniqueKey,
                "{}",
                DriftStatus.OPEN.name());
    }

    private Map<String, Object> driftReferences(String driftId) {
        return jdbcTemplate.queryForMap(
                "select asset_id, consumer_id, subscription_id from drift_record where drift_id = ?",
                driftId);
    }
}
