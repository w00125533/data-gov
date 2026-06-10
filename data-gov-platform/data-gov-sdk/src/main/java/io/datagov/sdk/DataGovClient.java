package io.datagov.sdk;

import io.datagov.common.dto.GovernanceDtos;

public interface DataGovClient {
    GovernanceDtos.SdkSubscriptionRegistrationResponse registerSubscriptions(
            GovernanceDtos.SdkSubscriptionRegistrationRequest request);

    GovernanceDtos.JobRegistrationResponse registerJob(GovernanceDtos.JobRegistrationRequest request);
}
