package io.datagov.sdk;

import io.datagov.common.dto.GovernanceDtos;
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
}
