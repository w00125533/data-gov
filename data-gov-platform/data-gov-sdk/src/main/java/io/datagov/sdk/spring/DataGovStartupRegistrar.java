package io.datagov.sdk.spring;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.sdk.DataGovClient;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.ApplicationListener;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;

public class DataGovStartupRegistrar implements ApplicationListener<ApplicationReadyEvent> {
    private final DataGovClient dataGovClient;
    private final DataGovProperties properties;

    public DataGovStartupRegistrar(DataGovClient dataGovClient, DataGovProperties properties) {
        this.dataGovClient = dataGovClient;
        this.properties = properties;
    }

    @Override
    public void onApplicationEvent(ApplicationReadyEvent event) {
        if (properties.subscriptions().isEmpty()) {
            return;
        }

        try {
            dataGovClient.registerSubscriptions(toRequest());
        } catch (RuntimeException exception) {
            if (properties.failFast()) {
                throw exception;
            }
        }
    }

    GovernanceDtos.SdkSubscriptionRegistrationRequest toRequest() {
        GovernanceDtos.ConsumerRequest consumer = toConsumerRequest(properties.consumer());
        List<GovernanceDtos.SubscriptionDeclarationRequest> declarations = properties.subscriptions().stream()
                .map(this::toSubscriptionRequest)
                .toList();
        return new GovernanceDtos.SdkSubscriptionRegistrationRequest(
                consumer,
                declarationHash(consumer, declarations),
                declarations
        );
    }

    private GovernanceDtos.ConsumerRequest toConsumerRequest(DataGovProperties.Consumer consumer) {
        return new GovernanceDtos.ConsumerRequest(
                consumer.name(),
                consumer.type(),
                consumer.owner(),
                consumer.environment(),
                consumer.version(),
                consumer.instanceId()
        );
    }

    private GovernanceDtos.SubscriptionDeclarationRequest toSubscriptionRequest(
            DataGovProperties.Subscription subscription) {
        return new GovernanceDtos.SubscriptionDeclarationRequest(
                subscription.assetCode(),
                subscription.usageMode(),
                subscription.purpose(),
                subscription.fields(),
                subscription.notifyOn()
        );
    }

    private String declarationHash(
            GovernanceDtos.ConsumerRequest consumer,
            List<GovernanceDtos.SubscriptionDeclarationRequest> declarations) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest((consumer.consumerName() + declarations).getBytes(StandardCharsets.UTF_8));
            return "sha256:" + HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException exception) {
            return "sha256:unavailable";
        }
    }
}
