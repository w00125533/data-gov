package io.datagov.server.lineage;

import io.datagov.common.dto.LineageDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LineageDirection;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class LineageDtosContractTest {
    @Test
    void impactRecordsAreAvailableFromCommonDtos() {
        Instant now = Instant.parse("2026-06-10T00:00:00Z");
        LineageDtos.LineageAssetNode root = new LineageDtos.LineageAssetNode(
                "asset_1",
                "ads_cell_profile",
                "ADS Cell Profile",
                AssetType.TABLE,
                AssetEngine.STARROCKS);
        LineageDtos.LineageGraphResponse graph = new LineageDtos.LineageGraphResponse(
                root,
                LineageDirection.DOWN,
                2,
                List.of(root),
                List.of());
        LineageDtos.ImpactSubscription subscription = new LineageDtos.ImpactSubscription(
                "sub_1",
                "ads_cell_profile",
                "consumer_1",
                "rno-dashboard",
                "API_QUERY",
                List.of("cell_id"),
                now);
        LineageDtos.ImpactQueryUsage queryUsage = new LineageDtos.ImpactQueryUsage(
                "query_1",
                "SQL",
                "SUCCESS",
                List.of("ads_cell_profile"),
                now);

        LineageDtos.ImpactResponse response = new LineageDtos.ImpactResponse(
                root,
                2,
                graph,
                List.of(subscription),
                List.of(queryUsage));

        assertThat(response.root()).isEqualTo(root);
        assertThat(response.downstreamLineage()).isEqualTo(graph);
        assertThat(response.subscriptions()).containsExactly(subscription);
        assertThat(response.recentQueries()).containsExactly(queryUsage);
    }
}
