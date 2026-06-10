package io.datagov.server.query;

import java.time.Duration;
import java.util.List;

public interface StarRocksQueryExecutor {
    QueryResult execute(String sql, List<Object> params, int maxRows, Duration timeout);
}
