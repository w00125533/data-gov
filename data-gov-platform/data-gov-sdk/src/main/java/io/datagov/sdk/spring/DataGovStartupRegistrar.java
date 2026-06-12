package io.datagov.sdk.spring;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.dto.MetadataDtos;
import io.datagov.common.enums.MetadataProducerType;
import io.datagov.common.enums.MetadataSyncMode;
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
        if (!properties.metadata().isEmpty()) {
            register(() -> dataGovClient.registerMetadataSnapshot(toMetadataRequest()));
        }

        if (!properties.subscriptions().isEmpty()) {
            register(() -> dataGovClient.registerSubscriptions(toRequest()));
        }
    }

    MetadataDtos.MetadataSnapshotRegisterRequest toMetadataRequest() {
        DataGovProperties.Consumer consumer = properties.consumer();
        MetadataDtos.ProducerRequest producer = new MetadataDtos.ProducerRequest(
                consumer.name(),
                MetadataProducerType.MICROSERVICE,
                consumer.owner(),
                consumer.environment(),
                consumer.instanceId()
        );
        List<MetadataDtos.MetadataItemRequest> metadataList = properties.metadata().stream()
                .map(this::toMetadataItemRequest)
                .toList();
        return new MetadataDtos.MetadataSnapshotRegisterRequest(
                producer,
                MetadataSyncMode.FULL,
                metadataList
        );
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

    private void register(Registration registration) {
        try {
            registration.run();
        } catch (RuntimeException exception) {
            if (properties.failFast()) {
                throw exception;
            }
        }
    }

    private MetadataDtos.MetadataItemRequest toMetadataItemRequest(DataGovProperties.Metadata metadata) {
        return new MetadataDtos.MetadataItemRequest(
                metadata.assetCode(),
                metadata.assetName(),
                metadata.metadataType(),
                metadata.sourceType(),
                metadata.domain(),
                metadata.owner(),
                metadata.description(),
                metadata.queryable(),
                metadata.federatedQueryable(),
                metadata.schema().stream()
                        .map(this::toMetadataFieldRequest)
                        .toList(),
                toMetadataBindingRequest(metadata.binding()),
                null
        );
    }

    private MetadataDtos.MetadataFieldRequest toMetadataFieldRequest(DataGovProperties.Field field) {
        return new MetadataDtos.MetadataFieldRequest(
                field.fieldName(),
                field.fieldType(),
                field.ordinal(),
                field.nullable(),
                field.partitionKey(),
                field.primaryKey(),
                field.eventTime(),
                field.description(),
                field.expression()
        );
    }

    private MetadataDtos.MetadataBindingRequest toMetadataBindingRequest(DataGovProperties.Binding binding) {
        if (binding == null) {
            return null;
        }

        return new MetadataDtos.MetadataBindingRequest(
                binding.sourceType(),
                binding.catalog(),
                binding.database(),
                binding.schema(),
                binding.table(),
                binding.topic(),
                binding.format(),
                binding.locationUri(),
                binding.connectionRef(),
                binding.queryAdapter(),
                binding.properties()
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

    private interface Registration {
        void run();
    }
}
