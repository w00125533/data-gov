package io.datagov.sdk.spring;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.sdk.DataGovClient;
import io.datagov.sdk.DefaultDataGovClient;
import io.datagov.sdk.notification.DataGovNotificationHandler;
import io.datagov.sdk.notification.DataGovNotificationListener;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Bean;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.kafka.annotation.EnableKafka;
import org.springframework.kafka.support.converter.RecordMessageConverter;
import org.springframework.kafka.support.converter.StringJsonMessageConverter;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.List;

@AutoConfiguration
@EnableConfigurationProperties(DataGovProperties.class)
public class DataGovAutoConfiguration {
    @Bean
    @ConditionalOnProperty(prefix = "data-gov", name = "enabled", havingValue = "true", matchIfMissing = true)
    @ConditionalOnMissingBean
    DataGovClient dataGovClient(DataGovProperties properties) {
        return new DefaultDataGovClient(RestClient.builder()
                .baseUrl(properties.endpoint())
                .requestFactory(requestFactory(properties))
                .build());
    }

    @Bean
    @ConditionalOnProperty(prefix = "data-gov", name = "enabled", havingValue = "true", matchIfMissing = true)
    @ConditionalOnMissingBean
    DataGovStartupRegistrar dataGovStartupRegistrar(DataGovClient dataGovClient, DataGovProperties properties) {
        return new DataGovStartupRegistrar(dataGovClient, properties);
    }

    @Bean
    @ConditionalOnProperty(prefix = "data-gov.notifications", name = "enabled", havingValue = "true")
    @ConditionalOnBean(DataGovNotificationHandler.class)
    @ConditionalOnMissingBean
    DataGovNotificationListener dataGovNotificationListener(List<DataGovNotificationHandler> handlers) {
        return new DataGovNotificationListener(handlers);
    }

    static SimpleClientHttpRequestFactory requestFactory(DataGovProperties properties) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        Duration timeout = Duration.ofMillis(properties.registerTimeoutMs());
        factory.setConnectTimeout(timeout);
        factory.setReadTimeout(timeout);
        return factory;
    }

    @Configuration(proxyBeanMethods = false)
    @EnableKafka
    @ConditionalOnProperty(prefix = "data-gov.notifications", name = "enabled", havingValue = "true")
    @ConditionalOnBean(DataGovNotificationHandler.class)
    static class DataGovKafkaConfiguration {
        @Bean
        @ConditionalOnMissingBean(RecordMessageConverter.class)
        RecordMessageConverter dataGovNotificationRecordMessageConverter(ObjectMapper objectMapper) {
            return new StringJsonMessageConverter(objectMapper);
        }
    }
}
