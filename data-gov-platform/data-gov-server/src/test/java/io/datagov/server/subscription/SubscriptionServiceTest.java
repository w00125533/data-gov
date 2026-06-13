package io.datagov.server.subscription;

import io.datagov.common.dto.FormalSubscriptionDtos;
import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.LifecycleStatus;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.common.enums.UsageMode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
@Transactional
class SubscriptionServiceTest {
    @Autowired
    private SubscriptionService subscriptionService;

    @Autowired
    private SubscriptionRepository subscriptionRepository;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void insertAssets() {
        insertAsset("asset_1", "ads_cell_profile");
        insertAsset("asset_2", "dwd_session_qos");
    }

    @Test
    void cancelSubscriptionsRejectsBlankConsumerIdWithoutCancellingAssetSubscriptions() {
        GovernanceDtos.SubscriptionResponse first = createSubscription("ads_cell_profile", "rno-dashboard");
        GovernanceDtos.SubscriptionResponse second = createSubscription("ads_cell_profile", "capacity-planner");

        assertThatThrownBy(() -> subscriptionRepository.cancelSubscriptionsForAssetAndConsumer(
                "asset_1",
                " ",
                Instant.parse("2026-06-13T00:00:00Z")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("consumerId is required");

        assertThat(subscriptionService.getSubscription(first.subscriptionId()).status()).isEqualTo(SubscriptionStatus.ACTIVE);
        assertThat(subscriptionService.getSubscription(second.subscriptionId()).status()).isEqualTo(SubscriptionStatus.ACTIVE);
    }

    @Test
    void cancelFormalSubscriptionsOnlyCancelsMatchingAssetAndConsumer() {
        GovernanceDtos.SubscriptionResponse target = createSubscription("ads_cell_profile", "rno-dashboard");
        GovernanceDtos.SubscriptionResponse otherConsumer = createSubscription("ads_cell_profile", "capacity-planner");
        GovernanceDtos.SubscriptionResponse otherAsset = createSubscription("dwd_session_qos", "rno-dashboard");

        FormalSubscriptionDtos.FormalCancelSubscriptionResponse response =
                subscriptionService.cancelFormalSubscriptions(
                        "asset_1",
                        new FormalSubscriptionDtos.FormalCancelSubscriptionRequest(
                                target.consumerId(),
                                "no longer needed",
                                "operator"));

        assertThat(response.metadataId()).isEqualTo("asset_1");
        assertThat(response.consumerId()).isEqualTo(target.consumerId());
        assertThat(response.cancelledSubscriptions())
                .extracting(FormalSubscriptionDtos.CancelledSubscriptionResponse::subscriptionId)
                .containsExactly(target.subscriptionId());

        assertThat(subscriptionService.getSubscription(target.subscriptionId()).status())
                .isEqualTo(SubscriptionStatus.CANCELLED);
        assertThat(subscriptionService.getSubscription(otherConsumer.subscriptionId()).status())
                .isEqualTo(SubscriptionStatus.ACTIVE);
        assertThat(subscriptionService.getSubscription(otherAsset.subscriptionId()).status())
                .isEqualTo(SubscriptionStatus.ACTIVE);
    }

    private GovernanceDtos.SubscriptionResponse createSubscription(String assetCode, String consumerName) {
        return subscriptionService.createSubscription(
                assetCode,
                new GovernanceDtos.CreateSubscriptionRequest(
                        new GovernanceDtos.ConsumerRequest(
                                consumerName,
                                ConsumerType.MICROSERVICE,
                                "team",
                                "prod",
                                null,
                                null),
                        new GovernanceDtos.SubscriptionDeclarationRequest(
                                assetCode,
                                UsageMode.API_QUERY,
                                "test coverage",
                                List.of("cell_id"),
                                List.of(AssetEventType.SCHEMA_CHANGE))));
    }

    private void insertAsset(String assetId, String assetCode) {
        Instant now = Instant.parse("2026-06-13T00:00:00Z");
        jdbcTemplate.update("""
                insert into data_asset (
                    asset_id, asset_code, asset_name, asset_type, engine, domain, owner, description,
                    lifecycle_status, schema_version, queryable, federated_queryable, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                assetId,
                assetCode,
                assetCode,
                AssetType.TABLE.name(),
                AssetEngine.STARROCKS.name(),
                "wireless",
                "network-team",
                "test asset",
                LifecycleStatus.ACTIVE.name(),
                1,
                true,
                true,
                Timestamp.from(now),
                Timestamp.from(now));
    }
}
