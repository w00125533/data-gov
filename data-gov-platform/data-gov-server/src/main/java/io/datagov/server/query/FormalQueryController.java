package io.datagov.server.query;

import io.datagov.common.dto.AssetDtos;
import io.datagov.common.dto.QueryDtos;
import io.datagov.server.asset.AssetNotFoundException;
import io.datagov.server.asset.AssetRepository;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/rest/oss/inner/modelengineservice/v1")
public class FormalQueryController {
    private static final String SUBSCRIPTION_HEADER = "X-DataGov-Subscription-Id";

    private final AssetRepository assetRepository;
    private final ProductQueryService productQueryService;
    private final SqlGatewayService sqlGatewayService;

    public FormalQueryController(
            AssetRepository assetRepository,
            ProductQueryService productQueryService,
            SqlGatewayService sqlGatewayService
    ) {
        this.assetRepository = assetRepository;
        this.productQueryService = productQueryService;
        this.sqlGatewayService = sqlGatewayService;
    }

    @PostMapping("/apiquery/{metadataId}")
    public QueryDtos.QueryResponse queryMetadata(
            @PathVariable("metadataId") String metadataId,
            @RequestHeader(name = SUBSCRIPTION_HEADER, required = false) String subscriptionId,
            @Valid @RequestBody(required = false) QueryDtos.AssetQueryRequest request
    ) {
        AssetDtos.AssetResponse asset = assetRepository.findAssetById(metadataId)
                .orElseThrow(() -> new AssetNotFoundException(metadataId));
        return productQueryService.query(asset.assetCode(), withHeaderSubscriptionId(request, subscriptionId));
    }

    @PostMapping("/sqlquery")
    public QueryDtos.QueryResponse querySql(@Valid @RequestBody QueryDtos.SqlQueryRequest request) {
        return sqlGatewayService.query(request);
    }

    private QueryDtos.AssetQueryRequest withHeaderSubscriptionId(
            QueryDtos.AssetQueryRequest request,
            String subscriptionId
    ) {
        if (subscriptionId == null || subscriptionId.isBlank()) {
            return request;
        }
        if (request == null) {
            return new QueryDtos.AssetQueryRequest(null, null, null, subscriptionId, null, null);
        }
        if (request.subscriptionId() != null && !request.subscriptionId().isBlank()) {
            return request;
        }
        return new QueryDtos.AssetQueryRequest(
                request.select(),
                request.filters(),
                request.limit(),
                subscriptionId,
                request.consumerName(),
                request.environment());
    }
}
