package io.datagov.server.query;

import io.datagov.common.dto.AssetDtos;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

@Component
public class StarRocksNameResolver {
    public String tableName(AssetDtos.PhysicalBindingResponse binding) {
        if (binding == null
                || !StringUtils.hasText(binding.catalogName())
                || !StringUtils.hasText(binding.databaseName())
                || !StringUtils.hasText(binding.tableName())) {
            throw new QueryValidationException(
                    "MISSING_PHYSICAL_BINDING",
                    "Asset does not have a complete active physical binding");
        }
        return quote(binding.catalogName()) + "." + quote(binding.databaseName()) + "." + quote(binding.tableName());
    }

    public String quote(String identifier) {
        if (!StringUtils.hasText(identifier) || identifier.contains("`")) {
            throw new QueryValidationException("INVALID_SQL", "Invalid StarRocks identifier");
        }
        return "`" + identifier + "`";
    }
}
