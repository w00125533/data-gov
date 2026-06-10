package io.datagov.server.query;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;

@Repository
public class QueryRecordRepository {
    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public QueryRecordRepository(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public void insert(QueryRecord record) {
        jdbcTemplate.update("""
                insert into query_record (
                    query_id, request_type, asset_id, subscription_id, consumer_id, referenced_asset_codes,
                    selected_fields, filter_json, sql_text, rewritten_sql, status, error_code, error_message,
                    row_count, elapsed_ms, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                record.queryId(),
                record.requestType().name(),
                record.assetId(),
                record.subscriptionId(),
                record.consumerId(),
                writeJson(record.referencedAssetCodes()),
                writeJson(record.selectedFields()),
                writeJson(record.filters()),
                record.sqlText(),
                record.rewrittenSql(),
                record.status().name(),
                record.errorCode(),
                record.errorMessage(),
                record.rowCount(),
                record.elapsedMs(),
                Timestamp.from(record.createdAt()));
    }

    private String writeJson(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception ex) {
            throw new QueryExecutionException("QUERY_EXECUTION_FAILED", "Failed to serialize query record JSON", ex);
        }
    }
}
