package io.datagov.sdk;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.dto.MetadataDtos;
import io.datagov.common.dto.QueryDtos;

public interface DataGovClient {
    MetadataDtos.MetadataSyncResponse registerMetadataSnapshot(
            MetadataDtos.MetadataSnapshotRegisterRequest request);

    GovernanceDtos.SdkSubscriptionRegistrationResponse registerSubscriptions(
            GovernanceDtos.SdkSubscriptionRegistrationRequest request);

    GovernanceDtos.JobRegistrationResponse registerJob(GovernanceDtos.JobRegistrationRequest request);

    AssetQueryBuilder asset(String assetCode);

    QueryDtos.QueryResponse sql(QueryDtos.SqlQueryRequest request);
}
