package io.datagov.server.query;

import io.datagov.common.dto.QueryDtos;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class QueryController {
    private final ProductQueryService productQueryService;
    private final SqlGatewayService sqlGatewayService;

    public QueryController(ProductQueryService productQueryService, SqlGatewayService sqlGatewayService) {
        this.productQueryService = productQueryService;
        this.sqlGatewayService = sqlGatewayService;
    }

    @PostMapping("/assets/{assetCode}/query")
    public QueryDtos.QueryResponse queryAsset(
            @PathVariable("assetCode") String assetCode,
            @Valid @RequestBody(required = false) QueryDtos.AssetQueryRequest request
    ) {
        return productQueryService.query(assetCode, request);
    }

    @PostMapping("/sql")
    public QueryDtos.QueryResponse querySql(@Valid @RequestBody QueryDtos.SqlQueryRequest request) {
        return sqlGatewayService.query(request);
    }
}
