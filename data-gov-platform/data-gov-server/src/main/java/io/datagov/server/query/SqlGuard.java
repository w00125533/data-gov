package io.datagov.server.query;

import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Component
public class SqlGuard {
    private static final Pattern WRITE_KEYWORDS = Pattern.compile(
            "(?i)\\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CALL|LOAD|EXPORT)\\b");
    private static final Pattern SOURCE_PATTERN = Pattern.compile("(?i)\\b(from|join)\\s+([^\\s,()]+)");
    private static final Pattern CTE_NAME_PATTERN = Pattern.compile("(?i)(?:\\bwith\\b|,)\\s+([A-Za-z_][A-Za-z0-9_]*)\\s+as\\s*\\(");
    private static final Pattern SIMPLE_IDENTIFIER = Pattern.compile("[A-Za-z_][A-Za-z0-9_]*");
    private static final Pattern FINAL_LIMIT = Pattern.compile("(?is)\\s+limit\\s+\\d+\\s*$");

    public String validateReadOnly(String sql) {
        if (sql == null || sql.isBlank()) {
            throw new QueryValidationException("INVALID_SQL", "SQL must not be blank");
        }
        String normalized = stripTrailingSemicolon(sql.trim());
        if (normalized.contains(";")) {
            throw new QueryValidationException("INVALID_SQL", "Multiple SQL statements are not allowed");
        }
        String lower = normalized.toLowerCase(Locale.ROOT);
        if (!lower.startsWith("select ") && !lower.startsWith("with ")) {
            throw new QueryValidationException("INVALID_SQL", "Only SELECT SQL is allowed");
        }
        if (WRITE_KEYWORDS.matcher(normalized).find()) {
            throw new QueryValidationException("INVALID_SQL", "Write and control SQL are not allowed");
        }
        return normalized;
    }

    public List<String> extractAssetCodes(String sql) {
        Matcher matcher = SOURCE_PATTERN.matcher(sql);
        Set<String> cteNames = extractCteNames(sql);
        Set<String> assetCodes = new LinkedHashSet<>();
        while (matcher.find()) {
            String token = matcher.group(2);
            if (!SIMPLE_IDENTIFIER.matcher(token).matches()) {
                throw new QueryValidationException("INVALID_SQL", "Only registered asset codes are allowed in FROM/JOIN");
            }
            if (!cteNames.contains(token.toLowerCase(Locale.ROOT))) {
                assetCodes.add(token);
            }
        }
        if (assetCodes.isEmpty()) {
            throw new QueryValidationException("INVALID_SQL", "SQL must reference at least one registered asset");
        }
        return new ArrayList<>(assetCodes);
    }

    public String rewriteSources(String sql, java.util.Map<String, String> physicalNames) {
        Matcher matcher = SOURCE_PATTERN.matcher(sql);
        Set<String> cteNames = extractCteNames(sql);
        StringBuilder rewritten = new StringBuilder();
        while (matcher.find()) {
            String assetCode = matcher.group(2);
            if (cteNames.contains(assetCode.toLowerCase(Locale.ROOT))) {
                matcher.appendReplacement(rewritten, matcher.group(1) + " " + assetCode);
                continue;
            }
            String physicalName = physicalNames.get(assetCode);
            if (physicalName == null) {
                throw new QueryValidationException("UNKNOWN_SQL_ASSET", "Unknown SQL asset: " + assetCode);
            }
            matcher.appendReplacement(rewritten, matcher.group(1) + " " + Matcher.quoteReplacement(physicalName));
        }
        matcher.appendTail(rewritten);
        return rewritten.toString();
    }

    public String forceLimit(String sql, Integer requestedLimit, int maxLimit) {
        int limit = Math.min(requestedLimit, maxLimit);
        String withoutLimit = FINAL_LIMIT.matcher(sql).replaceFirst("");
        return withoutLimit + " limit " + limit;
    }

    public String appendLimitIfMissing(String sql, int maxLimit) {
        if (FINAL_LIMIT.matcher(sql).find()) {
            return sql;
        }
        return sql + " limit " + maxLimit;
    }

    private String stripTrailingSemicolon(String sql) {
        if (sql.endsWith(";")) {
            return sql.substring(0, sql.length() - 1).trim();
        }
        return sql;
    }

    private Set<String> extractCteNames(String sql) {
        Matcher matcher = CTE_NAME_PATTERN.matcher(sql);
        Set<String> names = new LinkedHashSet<>();
        while (matcher.find()) {
            names.add(matcher.group(1).toLowerCase(Locale.ROOT));
        }
        return names;
    }
}
