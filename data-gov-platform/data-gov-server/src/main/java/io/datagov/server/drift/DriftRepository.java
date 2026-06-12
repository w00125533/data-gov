package io.datagov.server.drift;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.dto.DriftDtos;
import io.datagov.common.enums.DriftStatus;
import io.datagov.common.enums.DriftType;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.ConnectionCallback;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Savepoint;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public class DriftRepository {
    private static final TypeReference<Map<String, Object>> EVIDENCE_TYPE = new TypeReference<>() {
    };

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public DriftRepository(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public List<DriftCandidate> findDeclaredUnusedCandidates(Instant unusedCutoff) {
        try {
            return jdbcTemplate.query("""
                    select s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name,
                           s.last_runtime_seen_at, s.last_registered_at,
                           coalesce(q.query_count, 0) as query_count,
                           q.first_seen_at, q.last_seen_at
                    from subscription s
                    join data_asset a on a.asset_id = s.asset_id
                    join consumer c on c.consumer_id = s.consumer_id
                    left join (
                        select asset_id, consumer_id, count(*) as query_count,
                               min(created_at) as first_seen_at, max(created_at) as last_seen_at
                        from query_record
                        where status = 'SUCCESS'
                        group by asset_id, consumer_id
                    ) q on q.asset_id = s.asset_id and q.consumer_id = s.consumer_id
                    where s.status = 'ACTIVE'
                      and (s.last_runtime_seen_at is null or s.last_runtime_seen_at < ?)
                    order by s.created_at, s.subscription_id
                    """, candidateMapper(), Timestamp.from(unusedCutoff));
        } catch (DataAccessException ex) {
            throw new DriftDataAccessException("Failed to find declared-unused drift candidates", ex);
        }
    }

    public List<DriftCandidate> findUndeclaredUsageCandidates(Instant usageSince) {
        try {
            return jdbcTemplate.query("""
                    select null as subscription_id, q.asset_id, a.asset_code, q.consumer_id, c.consumer_name,
                           null as last_runtime_seen_at, null as last_registered_at,
                           count(*) as query_count,
                           min(q.created_at) as first_seen_at, max(q.created_at) as last_seen_at
                    from query_record q
                    join data_asset a on a.asset_id = q.asset_id
                    join consumer c on c.consumer_id = q.consumer_id
                    where q.status = 'SUCCESS'
                      and q.asset_id is not null
                      and q.consumer_id is not null
                      and q.created_at >= ?
                      and not exists (
                          select 1
                          from subscription s
                          where s.asset_id = q.asset_id
                            and s.consumer_id = q.consumer_id
                            and s.status = 'ACTIVE'
                      )
                    group by q.asset_id, a.asset_code, q.consumer_id, c.consumer_name
                    order by a.asset_code, c.consumer_name
                    """, candidateMapper(), Timestamp.from(usageSince));
        } catch (DataAccessException ex) {
            throw new DriftDataAccessException("Failed to find undeclared-usage drift candidates", ex);
        }
    }

    public List<DriftCandidate> findStaleDeclarationCandidates(Instant staleCutoff) {
        try {
            return jdbcTemplate.query("""
                    select s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name,
                           s.last_runtime_seen_at, s.last_registered_at,
                           coalesce(q.query_count, 0) as query_count,
                           q.first_seen_at, q.last_seen_at
                    from subscription s
                    join data_asset a on a.asset_id = s.asset_id
                    join consumer c on c.consumer_id = s.consumer_id
                    left join (
                        select asset_id, consumer_id, count(*) as query_count,
                               min(created_at) as first_seen_at, max(created_at) as last_seen_at
                        from query_record
                        where status = 'SUCCESS'
                        group by asset_id, consumer_id
                    ) q on q.asset_id = s.asset_id and q.consumer_id = s.consumer_id
                    where s.status = 'ACTIVE'
                      and s.last_registered_at < ?
                    order by s.created_at, s.subscription_id
                    """, candidateMapper(), Timestamp.from(staleCutoff));
        } catch (DataAccessException ex) {
            throw new DriftDataAccessException("Failed to find stale-declaration drift candidates", ex);
        }
    }

    public Optional<DriftDtos.DriftRecordResponse> findOpenByUniqueKey(String uniqueKey) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select d.drift_id, d.drift_type, d.status, d.asset_id, a.asset_code,
                           d.consumer_id, c.consumer_name, d.subscription_id, d.evidence,
                           d.detected_at, d.resolved_at
                    from drift_record d
                    left join data_asset a on a.asset_id = d.asset_id
                    left join consumer c on c.consumer_id = d.consumer_id
                    where d.unique_key = ? and d.status = 'OPEN'
                    """, recordMapper(), uniqueKey));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        } catch (DataAccessException ex) {
            throw new DriftDataAccessException("Failed to find open drift record by unique key", ex);
        }
    }

    public Optional<DriftDtos.DriftRecordResponse> findByUniqueKey(String uniqueKey) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select d.drift_id, d.drift_type, d.status, d.asset_id, a.asset_code,
                           d.consumer_id, c.consumer_name, d.subscription_id, d.evidence,
                           d.detected_at, d.resolved_at
                    from drift_record d
                    left join data_asset a on a.asset_id = d.asset_id
                    left join consumer c on c.consumer_id = d.consumer_id
                    where d.unique_key = ?
                    """, recordMapper(), uniqueKey));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        } catch (DataAccessException ex) {
            throw new DriftDataAccessException("Failed to find drift record by unique key", ex);
        }
    }

    public DriftDtos.DriftRecordResponse insertOpen(
            String driftId,
            DriftType driftType,
            DriftCandidate candidate,
            String uniqueKey,
            Map<String, Object> evidence,
            Instant detectedAt
    ) {
        try {
            jdbcTemplate.update("""
                    insert into drift_record (
                        drift_id, drift_type, asset_id, consumer_id, subscription_id, unique_key,
                        evidence, status, detected_at, resolved_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, null)
                    """,
                    driftId,
                    driftType.name(),
                    candidate.assetId(),
                    candidate.consumerId(),
                    candidate.subscriptionId(),
                    uniqueKey,
                    writeEvidence(evidence),
                    DriftStatus.OPEN.name(),
                    Timestamp.from(detectedAt));
            return findOpenByUniqueKey(uniqueKey).orElseThrow();
        } catch (DataAccessException ex) {
            throw new DriftDataAccessException("Failed to insert open drift record", ex);
        }
    }

    public UpsertedDriftRecord upsertOpen(
            String driftId,
            DriftType driftType,
            DriftCandidate candidate,
            String uniqueKey,
            Map<String, Object> evidence,
            Instant detectedAt
    ) {
        try {
            String evidenceJson = writeEvidence(evidence);
            boolean created = Boolean.TRUE.equals(jdbcTemplate.execute((ConnectionCallback<Boolean>) connection -> {
                Savepoint savepoint = connection.setSavepoint();
                try {
                    insertOpen(connection, driftId, driftType, candidate, uniqueKey, evidenceJson, detectedAt);
                    releaseSavepoint(connection, savepoint);
                    return true;
                } catch (SQLException ex) {
                    connection.rollback(savepoint);
                    releaseSavepoint(connection, savepoint);
                    if (!isUniqueViolation(ex)) {
                        throw ex;
                    }
                    refreshOrReopenByUniqueKey(connection, uniqueKey, evidenceJson, detectedAt);
                    return false;
                }
            }));
            DriftDtos.DriftRecordResponse record = findByUniqueKey(uniqueKey)
                    .orElseThrow(() -> new DriftDataAccessException(
                            "Failed to upsert drift record for unique key " + uniqueKey + ": row not found after upsert",
                            null));
            return new UpsertedDriftRecord(record, created && driftId.equals(record.driftId()));
        } catch (DriftDataAccessException ex) {
            throw ex;
        } catch (DataAccessException ex) {
            throw new DriftDataAccessException("Failed to upsert open drift record", ex);
        }
    }

    private void insertOpen(
            Connection connection,
            String driftId,
            DriftType driftType,
            DriftCandidate candidate,
            String uniqueKey,
            String evidence,
            Instant detectedAt
    ) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement("""
                insert into drift_record (
                    drift_id, drift_type, asset_id, consumer_id, subscription_id, unique_key,
                    evidence, status, detected_at, resolved_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, null)
                """)) {
            statement.setString(1, driftId);
            statement.setString(2, driftType.name());
            statement.setString(3, candidate.assetId());
            statement.setString(4, candidate.consumerId());
            statement.setString(5, candidate.subscriptionId());
            statement.setString(6, uniqueKey);
            statement.setString(7, evidence);
            statement.setString(8, DriftStatus.OPEN.name());
            statement.setTimestamp(9, Timestamp.from(detectedAt));
            statement.executeUpdate();
        }
    }

    private void refreshOrReopenByUniqueKey(
            Connection connection,
            String uniqueKey,
            String evidence,
            Instant detectedAt
    ) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement("""
                update drift_record
                set evidence = ?, detected_at = ?, status = ?, resolved_at = null
                where unique_key = ?
                """)) {
            statement.setString(1, evidence);
            statement.setTimestamp(2, Timestamp.from(detectedAt));
            statement.setString(3, DriftStatus.OPEN.name());
            statement.setString(4, uniqueKey);
            int updated = statement.executeUpdate();
            if (updated == 0) {
                throw new DriftDataAccessException(
                        "Failed to refresh or reopen drift record for unique key " + uniqueKey + ": no row updated",
                        null);
            }
        }
    }

    private boolean isUniqueViolation(SQLException ex) {
        return "23505".equals(ex.getSQLState());
    }

    private void releaseSavepoint(Connection connection, Savepoint savepoint) {
        try {
            connection.releaseSavepoint(savepoint);
        } catch (SQLException ignored) {
            // Some drivers release savepoints automatically after rollback.
        }
    }

    public DriftDtos.DriftRecordResponse refreshOpen(
            String uniqueKey,
            Map<String, Object> evidence,
            Instant detectedAt
    ) {
        try {
            int updated = jdbcTemplate.update("""
                    update drift_record
                    set evidence = ?, detected_at = ?
                    where unique_key = ? and status = 'OPEN'
                    """, writeEvidence(evidence), Timestamp.from(detectedAt), uniqueKey);
            if (updated == 0) {
                throw new DriftDataAccessException(
                        "Failed to refresh open drift record for unique key " + uniqueKey + ": no row updated",
                        null);
            }
            return findOpenByUniqueKey(uniqueKey)
                    .orElseThrow(() -> new DriftDataAccessException(
                            "Failed to refresh open drift record for unique key " + uniqueKey + ": row not found after update",
                            null));
        } catch (DriftDataAccessException ex) {
            throw ex;
        } catch (DataAccessException ex) {
            throw new DriftDataAccessException("Failed to refresh open drift record", ex);
        }
    }

    public DriftDtos.DriftRecordResponse refreshOrReopenByUniqueKey(
            String uniqueKey,
            Map<String, Object> evidence,
            Instant detectedAt
    ) {
        try {
            int updated = jdbcTemplate.update("""
                    update drift_record
                    set evidence = ?, detected_at = ?, status = ?, resolved_at = null
                    where unique_key = ?
                    """, writeEvidence(evidence), Timestamp.from(detectedAt), DriftStatus.OPEN.name(), uniqueKey);
            if (updated == 0) {
                throw new DriftDataAccessException(
                        "Failed to refresh or reopen drift record for unique key " + uniqueKey + ": no row updated",
                        null);
            }
            return findByUniqueKey(uniqueKey)
                    .orElseThrow(() -> new DriftDataAccessException(
                            "Failed to refresh or reopen drift record for unique key " + uniqueKey + ": row not found after update",
                            null));
        } catch (DriftDataAccessException ex) {
            throw ex;
        } catch (DataAccessException ex) {
            throw new DriftDataAccessException("Failed to refresh or reopen drift record", ex);
        }
    }

    public List<DriftDtos.DriftRecordResponse> listRecords() {
        try {
            return jdbcTemplate.query("""
                    select d.drift_id, d.drift_type, d.status, d.asset_id, a.asset_code,
                           d.consumer_id, c.consumer_name, d.subscription_id, d.evidence,
                           d.detected_at, d.resolved_at
                    from drift_record d
                    left join data_asset a on a.asset_id = d.asset_id
                    left join consumer c on c.consumer_id = d.consumer_id
                    order by d.detected_at, d.drift_id
                    """, recordMapper());
        } catch (DataAccessException ex) {
            throw new DriftDataAccessException("Failed to list drift records", ex);
        }
    }

    private RowMapper<DriftCandidate> candidateMapper() {
        return (rs, rowNum) -> new DriftCandidate(
                rs.getString("subscription_id"),
                rs.getString("asset_id"),
                rs.getString("asset_code"),
                rs.getString("consumer_id"),
                rs.getString("consumer_name"),
                toInstant(rs.getTimestamp("last_runtime_seen_at")),
                toInstant(rs.getTimestamp("last_registered_at")),
                rs.getLong("query_count"),
                toInstant(rs.getTimestamp("first_seen_at")),
                toInstant(rs.getTimestamp("last_seen_at")));
    }

    private RowMapper<DriftDtos.DriftRecordResponse> recordMapper() {
        return (rs, rowNum) -> new DriftDtos.DriftRecordResponse(
                rs.getString("drift_id"),
                DriftType.valueOf(rs.getString("drift_type")),
                DriftStatus.valueOf(rs.getString("status")),
                rs.getString("asset_id"),
                rs.getString("asset_code"),
                rs.getString("consumer_id"),
                rs.getString("consumer_name"),
                rs.getString("subscription_id"),
                readEvidence(rs.getString("evidence")),
                rs.getTimestamp("detected_at").toInstant(),
                toInstant(rs.getTimestamp("resolved_at")));
    }

    private String writeEvidence(Map<String, Object> evidence) {
        try {
            return objectMapper.writeValueAsString(evidence == null ? Map.of() : evidence);
        } catch (Exception ex) {
            throw new DriftDataAccessException("Failed to serialize drift evidence", ex);
        }
    }

    private Map<String, Object> readEvidence(String evidence) {
        if (evidence == null || evidence.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(evidence, EVIDENCE_TYPE);
        } catch (Exception ex) {
            throw new DriftDataAccessException("Failed to deserialize drift evidence", ex);
        }
    }

    private Instant toInstant(Timestamp timestamp) {
        return timestamp == null ? null : timestamp.toInstant();
    }

    public record DriftCandidate(
            String subscriptionId,
            String assetId,
            String assetCode,
            String consumerId,
            String consumerName,
            Instant lastRuntimeSeenAt,
            Instant lastRegisteredAt,
            long queryCount,
            Instant firstSeenAt,
            Instant lastSeenAt
    ) {
    }

    public record UpsertedDriftRecord(DriftDtos.DriftRecordResponse record, boolean created) {
    }
}
