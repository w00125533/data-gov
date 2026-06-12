package io.datagov.sdk.spring;

import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.UsageMode;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.List;
import java.util.Map;

@ConfigurationProperties(prefix = "data-gov")
public class DataGovProperties {
    private boolean enabled = true;
    private String endpoint = "http://localhost:8080";
    private Consumer consumer = new Consumer();
    private List<Subscription> subscriptions = List.of();
    private List<Metadata> metadata = List.of();
    private Notifications notifications = new Notifications();
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

    public List<Metadata> metadata() {
        return metadata;
    }

    public List<Metadata> getMetadata() {
        return metadata;
    }

    public void setMetadata(List<Metadata> metadata) {
        this.metadata = metadata == null ? List.of() : metadata;
    }

    public Notifications notifications() {
        return notifications;
    }

    public Notifications getNotifications() {
        return notifications;
    }

    public void setNotifications(Notifications notifications) {
        this.notifications = notifications == null ? new Notifications() : notifications;
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

    public static class Metadata {
        private String assetCode;
        private String assetName;
        private AssetType metadataType;
        private AssetEngine sourceType;
        private String domain;
        private String owner;
        private String description;
        private boolean queryable = true;
        private boolean federatedQueryable = true;
        private List<Field> schema = List.of();
        private Binding binding;

        public String assetCode() {
            return assetCode;
        }

        public String getAssetCode() {
            return assetCode;
        }

        public void setAssetCode(String assetCode) {
            this.assetCode = assetCode;
        }

        public String assetName() {
            return assetName;
        }

        public String getAssetName() {
            return assetName;
        }

        public void setAssetName(String assetName) {
            this.assetName = assetName;
        }

        public AssetType metadataType() {
            return metadataType;
        }

        public AssetType getMetadataType() {
            return metadataType;
        }

        public void setMetadataType(AssetType metadataType) {
            this.metadataType = metadataType;
        }

        public AssetEngine sourceType() {
            return sourceType;
        }

        public AssetEngine getSourceType() {
            return sourceType;
        }

        public void setSourceType(AssetEngine sourceType) {
            this.sourceType = sourceType;
        }

        public String domain() {
            return domain;
        }

        public String getDomain() {
            return domain;
        }

        public void setDomain(String domain) {
            this.domain = domain;
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

        public String description() {
            return description;
        }

        public String getDescription() {
            return description;
        }

        public void setDescription(String description) {
            this.description = description;
        }

        public boolean queryable() {
            return queryable;
        }

        public boolean isQueryable() {
            return queryable;
        }

        public void setQueryable(boolean queryable) {
            this.queryable = queryable;
        }

        public boolean federatedQueryable() {
            return federatedQueryable;
        }

        public boolean isFederatedQueryable() {
            return federatedQueryable;
        }

        public void setFederatedQueryable(boolean federatedQueryable) {
            this.federatedQueryable = federatedQueryable;
        }

        public List<Field> schema() {
            return schema;
        }

        public List<Field> getSchema() {
            return schema;
        }

        public void setSchema(List<Field> schema) {
            this.schema = schema == null ? List.of() : schema;
        }

        public Binding binding() {
            return binding;
        }

        public Binding getBinding() {
            return binding;
        }

        public void setBinding(Binding binding) {
            this.binding = binding;
        }
    }

    public static class Field {
        private String fieldName;
        private String fieldType;
        private Integer ordinal;
        private Boolean nullable;
        private Boolean partitionKey;
        private Boolean primaryKey;
        private Boolean eventTime;
        private String description;
        private String expression;

        public String fieldName() {
            return fieldName;
        }

        public String getFieldName() {
            return fieldName;
        }

        public void setFieldName(String fieldName) {
            this.fieldName = fieldName;
        }

        public String fieldType() {
            return fieldType;
        }

        public String getFieldType() {
            return fieldType;
        }

        public void setFieldType(String fieldType) {
            this.fieldType = fieldType;
        }

        public Integer ordinal() {
            return ordinal;
        }

        public Integer getOrdinal() {
            return ordinal;
        }

        public void setOrdinal(Integer ordinal) {
            this.ordinal = ordinal;
        }

        public Boolean nullable() {
            return nullable;
        }

        public Boolean getNullable() {
            return nullable;
        }

        public void setNullable(Boolean nullable) {
            this.nullable = nullable;
        }

        public Boolean partitionKey() {
            return partitionKey;
        }

        public Boolean getPartitionKey() {
            return partitionKey;
        }

        public void setPartitionKey(Boolean partitionKey) {
            this.partitionKey = partitionKey;
        }

        public Boolean primaryKey() {
            return primaryKey;
        }

        public Boolean getPrimaryKey() {
            return primaryKey;
        }

        public void setPrimaryKey(Boolean primaryKey) {
            this.primaryKey = primaryKey;
        }

        public Boolean eventTime() {
            return eventTime;
        }

        public Boolean getEventTime() {
            return eventTime;
        }

        public void setEventTime(Boolean eventTime) {
            this.eventTime = eventTime;
        }

        public String description() {
            return description;
        }

        public String getDescription() {
            return description;
        }

        public void setDescription(String description) {
            this.description = description;
        }

        public String expression() {
            return expression;
        }

        public String getExpression() {
            return expression;
        }

        public void setExpression(String expression) {
            this.expression = expression;
        }
    }

    public static class Binding {
        private AssetEngine sourceType;
        private String catalog;
        private String database;
        private String schema;
        private String table;
        private String topic;
        private String format;
        private String locationUri;
        private String connectionRef;
        private String queryAdapter;
        private Map<String, Object> properties = Map.of();

        public AssetEngine sourceType() {
            return sourceType;
        }

        public AssetEngine getSourceType() {
            return sourceType;
        }

        public void setSourceType(AssetEngine sourceType) {
            this.sourceType = sourceType;
        }

        public String catalog() {
            return catalog;
        }

        public String getCatalog() {
            return catalog;
        }

        public void setCatalog(String catalog) {
            this.catalog = catalog;
        }

        public String database() {
            return database;
        }

        public String getDatabase() {
            return database;
        }

        public void setDatabase(String database) {
            this.database = database;
        }

        public String schema() {
            return schema;
        }

        public String getSchema() {
            return schema;
        }

        public void setSchema(String schema) {
            this.schema = schema;
        }

        public String table() {
            return table;
        }

        public String getTable() {
            return table;
        }

        public void setTable(String table) {
            this.table = table;
        }

        public String topic() {
            return topic;
        }

        public String getTopic() {
            return topic;
        }

        public void setTopic(String topic) {
            this.topic = topic;
        }

        public String format() {
            return format;
        }

        public String getFormat() {
            return format;
        }

        public void setFormat(String format) {
            this.format = format;
        }

        public String locationUri() {
            return locationUri;
        }

        public String getLocationUri() {
            return locationUri;
        }

        public void setLocationUri(String locationUri) {
            this.locationUri = locationUri;
        }

        public String connectionRef() {
            return connectionRef;
        }

        public String getConnectionRef() {
            return connectionRef;
        }

        public void setConnectionRef(String connectionRef) {
            this.connectionRef = connectionRef;
        }

        public String queryAdapter() {
            return queryAdapter;
        }

        public String getQueryAdapter() {
            return queryAdapter;
        }

        public void setQueryAdapter(String queryAdapter) {
            this.queryAdapter = queryAdapter;
        }

        public Map<String, Object> properties() {
            return properties;
        }

        public Map<String, Object> getProperties() {
            return properties;
        }

        public void setProperties(Map<String, Object> properties) {
            this.properties = properties == null ? Map.of() : properties;
        }
    }

    public static class Notifications {
        private boolean enabled = false;
        private String topic = "data-gov.subscription-notifications";
        private String groupId = "data-gov-sdk";

        public boolean enabled() {
            return enabled;
        }

        public boolean isEnabled() {
            return enabled;
        }

        public void setEnabled(boolean enabled) {
            this.enabled = enabled;
        }

        public String topic() {
            return topic;
        }

        public String getTopic() {
            return topic;
        }

        public void setTopic(String topic) {
            this.topic = topic;
        }

        public String groupId() {
            return groupId;
        }

        public String getGroupId() {
            return groupId;
        }

        public void setGroupId(String groupId) {
            this.groupId = groupId;
        }
    }
}
