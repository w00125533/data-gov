package io.datagov.sdk;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.dto.QueryDtos;
import org.springframework.web.client.RestClient;

public class DefaultDataGovClient implements DataGovClient {
    private final RestClient restClient;

    public DefaultDataGovClient(RestClient restClient) {
        this.restClient = restClient;
    }

    @Override
    public GovernanceDtos.SdkSubscriptionRegistrationResponse registerSubscriptions(
            GovernanceDtos.SdkSubscriptionRegistrationRequest request) {
        try {
            return restClient.post()
                    .uri("/api/sdk/subscriptions/register")
                    .body(request)
                    .retrieve()
                    .body(GovernanceDtos.SdkSubscriptionRegistrationResponse.class);
        } catch (RuntimeException exception) {
            throw new DataGovClientException("Failed to register data governance subscriptions", exception);
        }
    }

    @Override
    public GovernanceDtos.JobRegistrationResponse registerJob(GovernanceDtos.JobRegistrationRequest request) {
        try {
            return restClient.post()
                    .uri("/api/sdk/jobs/register")
                    .body(request)
                    .retrieve()
                    .body(GovernanceDtos.JobRegistrationResponse.class);
        } catch (RuntimeException exception) {
            throw new DataGovClientException("Failed to register data governance job declaration", exception);
        }
    }

    @Override
    public AssetQueryBuilder asset(String assetCode) {
        return new AssetQueryBuilder(this, assetCode);
    }

    @Override
    public QueryDtos.QueryResponse sql(QueryDtos.SqlQueryRequest request) {
        try {
            return restClient.post()
                    .uri("/api/sql")
                    .body(request)
                    .retrieve()
                    .body(QueryDtos.QueryResponse.class);
        } catch (RuntimeException exception) {
            throw new DataGovClientException("Failed to execute data governance SQL query", exception);
        }
    }

    QueryDtos.QueryResponse queryAsset(String assetCode, QueryDtos.AssetQueryRequest request) {
        try {
            return restClient.post()
                    .uri("/api/assets/{assetCode}/query", assetCode)
                    .body(request)
                    .retrieve()
                    .body(QueryDtos.QueryResponse.class);
        } catch (RuntimeException exception) {
            throw new DataGovClientException("Failed to query asset " + assetCode, exception);
        }
    }
}
