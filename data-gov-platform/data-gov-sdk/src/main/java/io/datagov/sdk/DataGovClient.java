package io.datagov.sdk;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.dto.QueryDtos;

public interface DataGovClient {
    GovernanceDtos.SdkSubscriptionRegistrationResponse registerSubscriptions(
            GovernanceDtos.SdkSubscriptionRegistrationRequest request);

    GovernanceDtos.JobRegistrationResponse registerJob(GovernanceDtos.JobRegistrationRequest request);

    AssetQueryBuilder asset(String assetCode);

    QueryDtos.QueryResponse sql(QueryDtos.SqlQueryRequest request);
}
