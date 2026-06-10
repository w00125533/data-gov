package io.datagov.sdk.spring;

import io.datagov.sdk.DataGovClient;
import io.datagov.sdk.DefaultDataGovClient;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.web.client.RestClient;

@AutoConfiguration
@EnableConfigurationProperties(DataGovProperties.class)
@ConditionalOnProperty(prefix = "data-gov", name = "enabled", havingValue = "true", matchIfMissing = true)
public class DataGovAutoConfiguration {
    @Bean
    @ConditionalOnMissingBean
    DataGovClient dataGovClient(DataGovProperties properties) {
        return new DefaultDataGovClient(RestClient.builder().baseUrl(properties.endpoint()).build());
    }

    @Bean
    @ConditionalOnMissingBean
    DataGovStartupRegistrar dataGovStartupRegistrar(DataGovClient dataGovClient, DataGovProperties properties) {
        return new DataGovStartupRegistrar(dataGovClient, properties);
    }
}
