package io.datagov.server.event;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

@Component
@ConfigurationProperties(prefix = "data-gov.notifications")
public class NotificationProperties {
    private String kafkaTopic = "data-gov.subscription-notifications";

    public String topic() {
        return kafkaTopic;
    }

    public String getKafkaTopic() {
        return kafkaTopic;
    }

    public void setKafkaTopic(String kafkaTopic) {
        if (StringUtils.hasText(kafkaTopic)) {
            this.kafkaTopic = kafkaTopic;
        }
    }
}
