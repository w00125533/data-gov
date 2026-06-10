package io.datagov.sdk.spring;

import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.UsageMode;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.List;

@ConfigurationProperties(prefix = "data-gov")
public class DataGovProperties {
    private boolean enabled = true;
    private String endpoint = "http://localhost:8080";
    private Consumer consumer = new Consumer();
    private List<Subscription> subscriptions = List.of();
    private boolean failFast = false;
    private long registerTimeoutMs = 3000;

    public boolean enabled() {
        return enabled;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String endpoint() {
        return endpoint;
    }

    public String getEndpoint() {
        return endpoint;
    }

    public void setEndpoint(String endpoint) {
        this.endpoint = endpoint;
    }

    public Consumer consumer() {
        return consumer;
    }

    public Consumer getConsumer() {
        return consumer;
    }

    public void setConsumer(Consumer consumer) {
        this.consumer = consumer;
    }

    public List<Subscription> subscriptions() {
        return subscriptions;
    }

    public List<Subscription> getSubscriptions() {
        return subscriptions;
    }

    public void setSubscriptions(List<Subscription> subscriptions) {
        this.subscriptions = subscriptions;
    }

    public boolean failFast() {
        return failFast;
    }

    public boolean isFailFast() {
        return failFast;
    }

    public void setFailFast(boolean failFast) {
        this.failFast = failFast;
    }

    public long registerTimeoutMs() {
        return registerTimeoutMs;
    }

    public long getRegisterTimeoutMs() {
        return registerTimeoutMs;
    }

    public void setRegisterTimeoutMs(long registerTimeoutMs) {
        this.registerTimeoutMs = registerTimeoutMs;
    }

    public static class Consumer {
        private String name;
        private ConsumerType type = ConsumerType.MICROSERVICE;
        private String owner;
        private String environment = "default";
        private String version;
        private String instanceId;

        public String name() {
            return name;
        }

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public ConsumerType type() {
            return type;
        }

        public ConsumerType getType() {
            return type;
        }

        public void setType(ConsumerType type) {
            this.type = type;
        }

        public String owner() {
            return owner;
        }

        public String getOwner() {
            return owner;
        }

        public void setOwner(String owner) {
            this.owner = owner;
        }

        public String environment() {
            return environment;
        }

        public String getEnvironment() {
            return environment;
        }

        public void setEnvironment(String environment) {
            this.environment = environment;
        }

        public String version() {
            return version;
        }

        public String getVersion() {
            return version;
        }

        public void setVersion(String version) {
            this.version = version;
        }

        public String instanceId() {
            return instanceId;
        }

        public String getInstanceId() {
            return instanceId;
        }

        public void setInstanceId(String instanceId) {
            this.instanceId = instanceId;
        }
    }

    public static class Subscription {
        private String assetCode;
        private UsageMode usageMode;
        private String purpose;
        private List<String> fields = List.of();
        private List<AssetEventType> notifyOn = List.of();

        public String assetCode() {
            return assetCode;
        }

        public String getAssetCode() {
            return assetCode;
        }

        public void setAssetCode(String assetCode) {
            this.assetCode = assetCode;
        }

        public UsageMode usageMode() {
            return usageMode;
        }

        public UsageMode getUsageMode() {
            return usageMode;
        }

        public void setUsageMode(UsageMode usageMode) {
            this.usageMode = usageMode;
        }

        public String purpose() {
            return purpose;
        }

        public String getPurpose() {
            return purpose;
        }

        public void setPurpose(String purpose) {
            this.purpose = purpose;
        }

        public List<String> fields() {
            return fields;
        }

        public List<String> getFields() {
            return fields;
        }

        public void setFields(List<String> fields) {
            this.fields = fields;
        }

        public List<AssetEventType> notifyOn() {
            return notifyOn;
        }

        public List<AssetEventType> getNotifyOn() {
            return notifyOn;
        }

        public void setNotifyOn(List<AssetEventType> notifyOn) {
            this.notifyOn = notifyOn;
        }
    }
}
