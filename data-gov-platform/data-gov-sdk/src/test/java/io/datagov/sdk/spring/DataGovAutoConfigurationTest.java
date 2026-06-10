package io.datagov.sdk.spring;

import io.datagov.sdk.DataGovClient;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.assertj.core.api.Assertions.assertThat;

class DataGovAutoConfigurationTest {
    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withConfiguration(AutoConfigurations.of(DataGovAutoConfiguration.class));

    @Test
    void createsClientWhenEnabled() {
        contextRunner
                .withPropertyValues(
                        "data-gov.enabled=true",
                        "data-gov.endpoint=http://data-gov-server:8080",
                        "data-gov.consumer.name=rno-dashboard",
                        "data-gov.consumer.type=MICROSERVICE",
                        "data-gov.consumer.environment=prod",
                        "data-gov.subscriptions[0].asset-code=ads_cell_profile",
                        "data-gov.subscriptions[0].usage-mode=API_QUERY",
                        "data-gov.subscriptions[0].purpose=dashboard",
                        "data-gov.subscriptions[0].fields[0]=cell_id",
                        "data-gov.subscriptions[0].notify-on[0]=SCHEMA_CHANGE"
                )
                .run(context -> {
                    assertThat(context).hasSingleBean(DataGovClient.class);
                    assertThat(context).hasSingleBean(DataGovStartupRegistrar.class);

                    DataGovProperties properties = context.getBean(DataGovProperties.class);
                    assertThat(properties.consumer().name()).isEqualTo("rno-dashboard");
                    assertThat(properties.subscriptions()).hasSize(1);
                });
    }

    @Test
    void backsOffWhenDisabled() {
        contextRunner
                .withPropertyValues("data-gov.enabled=false")
                .run(context -> {
                    assertThat(context).doesNotHaveBean(DataGovClient.class);
                    assertThat(context).doesNotHaveBean(DataGovStartupRegistrar.class);
                });
    }
}
