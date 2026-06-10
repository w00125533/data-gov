package io.datagov.server.query;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.util.StringUtils;

@Configuration
@EnableConfigurationProperties(StarRocksQueryProperties.class)
public class StarRocksQueryConfiguration {
    @Bean
    public StarRocksQueryExecutor starRocksQueryExecutor(StarRocksQueryProperties properties) {
        if (StringUtils.hasText(properties.getJdbcUrl())) {
            return new JdbcStarRocksQueryExecutor(properties);
        }
        return (sql, params, maxRows, timeout) -> {
            throw new QueryExecutionException(
                    "STARROCKS_NOT_CONFIGURED",
                    "StarRocks JDBC URL is not configured");
        };
    }
}
