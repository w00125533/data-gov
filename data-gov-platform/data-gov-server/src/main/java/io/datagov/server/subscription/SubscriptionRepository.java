package io.datagov.server.subscription;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.JobStatus;
import io.datagov.common.enums.JobType;
import io.datagov.common.enums.SubscriptionSourceType;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.common.enums.UsageMode;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public class SubscriptionRepository {
    private static final TypeReference<List<String>> STRING_LIST_TYPE = new TypeReference<>() {
    };
    private static final TypeReference<List<AssetEventType>> EVENT_LIST_TYPE = new TypeReference<>() {
    };

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public SubscriptionRepository(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public Optional<AssetRef> findAssetId(String assetCode) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select asset_id, asset_code
                    from data_asset
                    where asset_code = ?
                    """, (rs, rowNum) -> new AssetRef(rs.getString("asset_id"), rs.getString("asset_code")), assetCode));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    public GovernanceDtos.ConsumerResponse upsertConsumer(
            String consumerId,
            GovernanceDtos.ConsumerRequest request,
            String declarationHash,
            Instant now
    ) {
        String environment = defaultEnvironment(request.environment());
        Optional<GovernanceDtos.ConsumerResponse> existing = findConsumer(request.consumerName(), environment);
        if (existing.isEmpty()) {
            jdbcTemplate.update("""
                    insert into consumer (
                        consumer_id, consumer_type, consumer_name, owner, environment, runtime_version, instance_id,
                        declaration_hash, last_registered_at, last_seen_at, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    consumerId, request.consumerType().name(), request.consumerName(), request.owner(), environment,
                    request.runtimeVersion(), request.instanceId(), declarationHash, Timestamp.from(now),
                    Timestamp.from(now), Timestamp.from(now), Timestamp.from(now));
            return findConsumer(request.consumerName(), environment).orElseThrow();
        }

        jdbcTemplate.update("""
                update consumer
                set consumer_type = ?, owner = ?, runtime_version = ?, instance_id = ?, declaration_hash = ?,
                    last_registered_at = ?, last_seen_at = ?, updated_at = ?
                where consumer_id = ?
                """,
                request.consumerType().name(), request.owner(), request.runtimeVersion(), request.instanceId(),
                declarationHash, Timestamp.from(now), Timestamp.from(now), Timestamp.from(now),
                existing.get().consumerId());
        return findConsumer(request.consumerName(), environment).orElseThrow();
    }

    public Optional<GovernanceDtos.ConsumerResponse> findConsumer(String consumerName, String environment) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select consumer_id, consumer_type, consumer_name, owner, environment, runtime_version, instance_id,
                           declaration_hash, last_registered_at, last_seen_at
                    from consumer
                    where consumer_name = ? and environment = ?
                    """, consumerMapper(), consumerName, defaultEnvironment(environment)));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    public GovernanceDtos.SubscriptionResponse upsertSubscription(
            String subscriptionId,
            String assetId,
            String consumerId,
            UsageMode usageMode,
            String purpose,
            List<String> fields,
            List<AssetEventType> notifyOn,
            SubscriptionSourceType sourceType,
            String declarationHash,
            Instant now
    ) {
        Optional<String> existingId = findSubscriptionId(assetId, consumerId, usageMode);
        if (existingId.isEmpty()) {
            jdbcTemplate.update("""
                    insert into subscription (
                        subscription_id, asset_id, consumer_id, usage_mode, purpose, declared_fields, notify_on,
                        source_type, declaration_hash, last_registered_at, status, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    subscriptionId, assetId, consumerId, usageMode.name(), purpose, writeList(fields),
                    writeList(notifyOn), sourceType.name(), declarationHash, Timestamp.from(now),
                    SubscriptionStatus.ACTIVE.name(), Timestamp.from(now), Timestamp.from(now));
            return findSubscription(subscriptionId).orElseThrow();
        }

        jdbcTemplate.update("""
                update subscription
                set purpose = ?, declared_fields = ?, notify_on = ?, source_type = ?, declaration_hash = ?,
                    last_registered_at = ?, status = ?, updated_at = ?
                where subscription_id = ?
                """,
                purpose, writeList(fields), writeList(notifyOn), sourceType.name(), declarationHash,
                Timestamp.from(now), SubscriptionStatus.ACTIVE.name(), Timestamp.from(now), existingId.get());
        return findSubscription(existingId.get()).orElseThrow();
    }

    public List<GovernanceDtos.SubscriptionResponse> listSubscriptions() {
        return jdbcTemplate.query("""
                select s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name, s.usage_mode,
                       s.purpose, s.declared_fields, s.notify_on, s.source_type, s.status, s.declaration_hash,
                       s.last_registered_at, s.last_runtime_seen_at, s.created_at, s.updated_at
                from subscription s
                join data_asset a on a.asset_id = s.asset_id
                join consumer c on c.consumer_id = s.consumer_id
                order by s.created_at, s.subscription_id
                """, subscriptionMapper());
    }

    public List<GovernanceDtos.SubscriptionResponse> listSubscriptionsForAsset(
            String assetId,
            String consumerId,
            SubscriptionStatus status
    ) {
        List<Object> args = new ArrayList<>();
        args.add(assetId);
        StringBuilder sql = new StringBuilder("""
                select s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name, s.usage_mode,
                       s.purpose, s.declared_fields, s.notify_on, s.source_type, s.status, s.declaration_hash,
                       s.last_registered_at, s.last_runtime_seen_at, s.created_at, s.updated_at
                from subscription s
                join data_asset a on a.asset_id = s.asset_id
                join consumer c on c.consumer_id = s.consumer_id
                where s.asset_id = ?
                """);
        if (consumerId != null && !consumerId.isBlank()) {
            sql.append(" and s.consumer_id = ?");
            args.add(consumerId);
        }
        if (status != null) {
            sql.append(" and s.status = ?");
            args.add(status.name());
        }
        sql.append(" order by s.created_at, s.subscription_id");
        return jdbcTemplate.query(sql.toString(), subscriptionMapper(), args.toArray());
    }

    public List<GovernanceDtos.SubscriptionResponse> cancelSubscriptionsForAssetAndConsumer(
            String assetId,
            String consumerId,
            Instant now
    ) {
        List<GovernanceDtos.SubscriptionResponse> current = listSubscriptionsForAsset(assetId, consumerId, null).stream()
                .filter(subscription -> subscription.status() != SubscriptionStatus.CANCELLED)
                .filter(subscription -> subscription.status() != SubscriptionStatus.REMOVED_BY_SNAPSHOT)
                .toList();
        for (GovernanceDtos.SubscriptionResponse subscription : current) {
            jdbcTemplate.update("""
                    update subscription
                    set status = ?, updated_at = ?
                    where subscription_id = ?
                    """,
                    SubscriptionStatus.CANCELLED.name(),
                    Timestamp.from(now),
                    subscription.subscriptionId());
        }
        return current.stream()
                .map(subscription -> findSubscription(subscription.subscriptionId()).orElseThrow())
                .toList();
    }

    public Optional<GovernanceDtos.SubscriptionResponse> findSubscription(String subscriptionId) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name, s.usage_mode,
                           s.purpose, s.declared_fields, s.notify_on, s.source_type, s.status, s.declaration_hash,
                           s.last_registered_at, s.last_runtime_seen_at, s.created_at, s.updated_at
                    from subscription s
                    join data_asset a on a.asset_id = s.asset_id
                    join consumer c on c.consumer_id = s.consumer_id
                    where s.subscription_id = ?
                    """, subscriptionMapper(), subscriptionId));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    public void updateLastRuntimeSeenAt(String subscriptionId, Instant now) {
        jdbcTemplate.update("""
                update subscription
                set last_runtime_seen_at = ?, updated_at = ?
                where subscription_id = ?
                """, Timestamp.from(now), Timestamp.from(now), subscriptionId);
    }

    public GovernanceDtos.SubscriptionResponse updateSubscription(
            String subscriptionId,
            GovernanceDtos.UpdateSubscriptionRequest request,
            Instant now
    ) {
        jdbcTemplate.update("""
                update subscription
                set usage_mode = case when ? then ? else usage_mode end,
                    purpose = case when ? then ? else purpose end,
                    declared_fields = case when ? then ? else declared_fields end,
                    notify_on = case when ? then ? else notify_on end,
                    status = case when ? then ? else status end,
                    updated_at = ?
                where subscription_id = ?
                """,
                request.usageMode() != null, request.usageMode() == null ? null : request.usageMode().name(),
                request.purpose() != null, request.purpose(),
                request.fields() != null, request.fields() == null ? null : writeList(request.fields()),
                request.notifyOn() != null, request.notifyOn() == null ? null : writeList(request.notifyOn()),
                request.status() != null, request.status() == null ? null : request.status().name(),
                Timestamp.from(now), subscriptionId);
        return findSubscription(subscriptionId).orElseThrow();
    }

    public JobRef upsertJob(
            String jobId,
            String consumerId,
            GovernanceDtos.JobRegistrationRequest request,
            Instant now
    ) {
        Optional<String> existingId = findJobId(consumerId, request.jobName(), request.jobType());
        if (existingId.isEmpty()) {
            jdbcTemplate.update("""
                    insert into consumer_job (
                        job_id, consumer_id, job_name, job_type, owner, code_ref, runtime_config, input_asset_codes,
                        output_asset_codes, declaration_hash, status, last_registered_at, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    jobId, consumerId, request.jobName(), request.jobType().name(), request.owner(), request.codeRef(),
                    writeMap(request.runtimeConfig()), writeList(request.inputAssets()), writeList(request.outputAssets()),
                    request.declarationHash(), JobStatus.ACTIVE.name(), Timestamp.from(now), Timestamp.from(now),
                    Timestamp.from(now));
            return findJob(jobId).orElseThrow();
        }

        jdbcTemplate.update("""
                update consumer_job
                set owner = ?, code_ref = ?, runtime_config = ?, input_asset_codes = ?, output_asset_codes = ?,
                    declaration_hash = ?, status = ?, last_registered_at = ?, updated_at = ?
                where job_id = ?
                """,
                request.owner(), request.codeRef(), writeMap(request.runtimeConfig()), writeList(request.inputAssets()),
                writeList(request.outputAssets()), request.declarationHash(), JobStatus.ACTIVE.name(),
                Timestamp.from(now), Timestamp.from(now), existingId.get());
        return findJob(existingId.get()).orElseThrow();
    }

    private Optional<String> findSubscriptionId(String assetId, String consumerId, UsageMode usageMode) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select subscription_id
                    from subscription
                    where asset_id = ? and consumer_id = ? and usage_mode = ?
                    """, String.class, assetId, consumerId, usageMode.name()));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    private Optional<String> findJobId(String consumerId, String jobName, JobType jobType) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select job_id
                    from consumer_job
                    where consumer_id = ? and job_name = ? and job_type = ?
                    """, String.class, consumerId, jobName, jobType.name()));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    private Optional<JobRef> findJob(String jobId) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select job_id, job_name, job_type, status, last_registered_at
                    from consumer_job
                    where job_id = ?
                    """, (rs, rowNum) -> new JobRef(
                    rs.getString("job_id"),
                    rs.getString("job_name"),
                    JobType.valueOf(rs.getString("job_type")),
                    JobStatus.valueOf(rs.getString("status")),
                    toInstant(rs.getTimestamp("last_registered_at"))), jobId));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    private RowMapper<GovernanceDtos.ConsumerResponse> consumerMapper() {
        return (rs, rowNum) -> new GovernanceDtos.ConsumerResponse(
                rs.getString("consumer_id"),
                ConsumerType.valueOf(rs.getString("consumer_type")),
                rs.getString("consumer_name"),
                rs.getString("owner"),
                rs.getString("environment"),
                rs.getString("runtime_version"),
                rs.getString("instance_id"),
                rs.getString("declaration_hash"),
                toInstant(rs.getTimestamp("last_registered_at")),
                toInstant(rs.getTimestamp("last_seen_at")));
    }

    private RowMapper<GovernanceDtos.SubscriptionResponse> subscriptionMapper() {
        return (rs, rowNum) -> new GovernanceDtos.SubscriptionResponse(
                rs.getString("subscription_id"),
                rs.getString("asset_id"),
                rs.getString("asset_code"),
                rs.getString("consumer_id"),
                rs.getString("consumer_name"),
                UsageMode.valueOf(rs.getString("usage_mode")),
                rs.getString("purpose"),
                readStringList(rs.getString("declared_fields")),
                readEventList(rs.getString("notify_on")),
                SubscriptionSourceType.valueOf(rs.getString("source_type")),
                SubscriptionStatus.valueOf(rs.getString("status")),
                rs.getString("declaration_hash"),
                toInstant(rs.getTimestamp("last_registered_at")),
                toInstant(rs.getTimestamp("last_runtime_seen_at")),
                rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at").toInstant());
    }

    private String defaultEnvironment(String environment) {
        return environment == null || environment.isBlank() ? "default" : environment;
    }

    private String writeList(Object value) {
        try {
            return objectMapper.writeValueAsString(value == null ? List.of() : value);
        } catch (Exception ex) {
            throw new SubscriptionDataAccessException("Failed to serialize subscription JSON list", ex);
        }
    }

    private String writeMap(Map<String, Object> value) {
        try {
            return objectMapper.writeValueAsString(value == null ? Map.of() : value);
        } catch (Exception ex) {
            throw new SubscriptionDataAccessException("Failed to serialize subscription JSON map", ex);
        }
    }

    private List<String> readStringList(String value) {
        if (value == null || value.isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(value, STRING_LIST_TYPE);
        } catch (Exception ex) {
            throw new SubscriptionDataAccessException("Failed to deserialize subscription string list", ex);
        }
    }

    private List<AssetEventType> readEventList(String value) {
        if (value == null || value.isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(value, EVENT_LIST_TYPE);
        } catch (Exception ex) {
            throw new SubscriptionDataAccessException("Failed to deserialize subscription event list", ex);
        }
    }

    private Instant toInstant(Timestamp timestamp) {
        return timestamp == null ? null : timestamp.toInstant();
    }

    public record AssetRef(String assetId, String assetCode) {
    }

    public record JobRef(
            String jobId,
            String jobName,
            JobType jobType,
            JobStatus status,
            Instant lastRegisteredAt
    ) {
    }
}
