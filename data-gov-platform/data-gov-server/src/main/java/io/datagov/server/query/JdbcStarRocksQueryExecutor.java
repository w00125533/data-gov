package io.datagov.server.query;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class JdbcStarRocksQueryExecutor implements StarRocksQueryExecutor {
    private final StarRocksQueryProperties properties;

    public JdbcStarRocksQueryExecutor(StarRocksQueryProperties properties) {
        this.properties = properties;
    }

    @Override
    public QueryResult execute(String sql, List<Object> params, int maxRows, Duration timeout) {
        try (Connection connection = DriverManager.getConnection(
                properties.getJdbcUrl(),
                properties.getUsername(),
                properties.getPassword());
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setMaxRows(maxRows);
            statement.setQueryTimeout((int) timeout.toSeconds());
            for (int index = 0; index < params.size(); index++) {
                statement.setObject(index + 1, params.get(index));
            }
            try (ResultSet resultSet = statement.executeQuery()) {
                ResultSetMetaData metaData = resultSet.getMetaData();
                List<String> columns = new ArrayList<>();
                for (int index = 1; index <= metaData.getColumnCount(); index++) {
                    columns.add(metaData.getColumnLabel(index));
                }
                List<Map<String, Object>> rows = new ArrayList<>();
                while (resultSet.next()) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (int index = 1; index <= metaData.getColumnCount(); index++) {
                        row.put(columns.get(index - 1), resultSet.getObject(index));
                    }
                    rows.add(row);
                }
                return new QueryResult(columns, rows);
            }
        } catch (Exception ex) {
            throw new QueryExecutionException("QUERY_EXECUTION_FAILED", "StarRocks query failed", ex);
        }
    }
}
