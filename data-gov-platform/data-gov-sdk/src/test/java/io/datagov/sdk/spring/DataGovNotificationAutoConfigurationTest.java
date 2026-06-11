package io.datagov.sdk.spring;

import io.datagov.sdk.notification.DataGovNotificationHandler;
import io.datagov.sdk.notification.DataGovNotificationListener;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.jackson.JacksonAutoConfiguration;
import org.springframework.boot.autoconfigure.kafka.KafkaAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.kafka.support.converter.RecordMessageConverter;
import org.springframework.kafka.support.converter.StringJsonMessageConverter;

import static org.assertj.core.api.Assertions.assertThat;

class DataGovNotificationAutoConfigurationTest {
    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withConfiguration(AutoConfigurations.of(
                    DataGovAutoConfiguration.class,
                    JacksonAutoConfiguration.class,
                    KafkaAutoConfiguration.class))
            .withPropertyValues("spring.kafka.listener.auto-startup=false");

    @Test
    void doesNotCreateNotificationListenerByDefault() {
        contextRunner
                .withBean(DataGovNotificationHandler.class, () -> message -> {
                })
                .run(context -> {
                    assertThat(context).doesNotHaveBean(DataGovNotificationListener.class);
                    assertThat(context).doesNotHaveBean(RecordMessageConverter.class);
                    KafkaListenerEndpointRegistry registry = context.getBean(KafkaListenerEndpointRegistry.class);
                    assertThat(registry.getListenerContainers()).isEmpty();
                });
    }

    @Test
    void createsNotificationListenerWhenEnabledAndHandlerExists() {
        contextRunner
                .withBean(DataGovNotificationHandler.class, () -> message -> {
                })
                .withPropertyValues(
                        "data-gov.notifications.enabled=true",
                        "data-gov.notifications.topic=data-gov.subscription-notifications",
                        "data-gov.notifications.group-id=rno-dashboard")
                .run(context -> {
                    assertThat(context).hasSingleBean(DataGovNotificationListener.class);
                    assertThat(context).hasSingleBean(RecordMessageConverter.class);
                    assertThat(context.getBean(RecordMessageConverter.class))
                            .isInstanceOf(StringJsonMessageConverter.class);
                    KafkaListenerEndpointRegistry registry = context.getBean(KafkaListenerEndpointRegistry.class);
                    assertThat(registry.getListenerContainers()).hasSize(1);
                    DataGovProperties properties = context.getBean(DataGovProperties.class);
                    assertThat(properties.notifications().topic()).isEqualTo("data-gov.subscription-notifications");
                    assertThat(properties.notifications().groupId()).isEqualTo("rno-dashboard");
                });
    }

    @Test
    void createsNotificationListenerWhenRegistrationIsDisabled() {
        contextRunner
                .withBean(DataGovNotificationHandler.class, () -> message -> {
                })
                .withPropertyValues(
                        "data-gov.enabled=false",
                        "data-gov.notifications.enabled=true")
                .run(context -> assertThat(context).hasSingleBean(DataGovNotificationListener.class));
    }

    @Test
    void doesNotCreateNotificationListenerWhenEnabledWithoutHandler() {
        contextRunner
                .withPropertyValues("data-gov.notifications.enabled=true")
                .run(context -> assertThat(context).doesNotHaveBean(DataGovNotificationListener.class));
    }
}
