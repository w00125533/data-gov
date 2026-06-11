# 数据治理架构视图

本文使用 Mermaid 描述数据治理平台的用例视图、逻辑视图、数据模型视图、运行时序视图、技术视图和部署视图。

## 1. 用例视图

```mermaid
flowchart LR
    Producer[数据生产方微服务 / Flink / Spark]
    Consumer[数据消费者微服务 / 分析服务]
    Admin[治理管理员]
    SDK[Java SDK]
    Platform[数据治理平台]

    Producer --> SDK
    Consumer --> SDK
    SDK --> Register((启动时元数据快照同步))
    SDK --> Subscribe((声明订阅))
    SDK --> Notify((监听变化通知))
    Consumer --> ApiQuery((产品 API 查询))
    Consumer --> SqlQuery((SQL Gateway 查询))
    Admin --> Discover((元数据发现))
    Admin --> Lineage((血缘查询))
    Admin --> RuntimeChange((运行时修改 / 取消注册))

    Register --> Platform
    Subscribe --> Platform
    Notify --> Platform
    ApiQuery --> Platform
    SqlQuery --> Platform
    Discover --> Platform
    Lineage --> Platform
    RuntimeChange --> Platform
```

## 2. 逻辑视图

```mermaid
classDiagram
    class MetadataController
    class SubscriptionController
    class QueryController
    class MetadataService
    class SubscriptionService
    class QueryService
    class LineageService
    class NotificationService
    class DriftService
    class StarRocksGateway
    class KafkaPublisher
    class GaussDBRepository

    MetadataController --> MetadataService
    MetadataController --> LineageService
    SubscriptionController --> SubscriptionService
    QueryController --> QueryService

    MetadataService --> GaussDBRepository
    MetadataService --> NotificationService
    MetadataService --> LineageService
    SubscriptionService --> GaussDBRepository
    QueryService --> StarRocksGateway
    QueryService --> GaussDBRepository
    LineageService --> GaussDBRepository
    NotificationService --> GaussDBRepository
    NotificationService --> KafkaPublisher
    DriftService --> GaussDBRepository
```

职责说明：

- `MetadataService` 负责启动快照同步、运行时修改、运行时取消注册、字段、物理绑定和事件生成。
- `LineageService` 负责表级和字段级血缘维护与查询。
- `SubscriptionService` 负责订阅声明、查询和取消。
- `QueryService` 负责产品 API 查询、SQL Gateway 查询和 `query_record` 写入。
- `NotificationService` 将 `metadata_event` 转换为订阅通知并发送 Kafka。
- `DriftService` 分析声明态和运行态差异。

## 3. 数据模型视图

```mermaid
erDiagram
    metadata {
      varchar metadata_id PK
      varchar asset_code UK
      varchar asset_type
      varchar service_name
      varchar environment
      varchar status
    }
    metadata_field {
      varchar field_id PK
      varchar metadata_id FK
      varchar field_name
      varchar field_type
    }
    metadata_binding {
      varchar binding_id PK
      varchar metadata_id FK
      varchar source_type
      varchar qualified_name
    }
    lineage_edge {
      varchar lineage_id PK
      varchar source_metadata_id FK
      varchar target_metadata_id FK
      varchar lineage_type
    }
    consumer {
      varchar consumer_id PK
      varchar consumer_name
      varchar consumer_type
      varchar environment
    }
    subscription {
      varchar subscription_id PK
      varchar metadata_id FK
      varchar consumer_id FK
      varchar usage_mode
      varchar status
    }
    query_record {
      varchar query_record_id PK
      varchar consumer_id FK
      varchar subscription_id FK
      jsonb referenced_asset_codes
    }
    metadata_event {
      varchar event_id PK
      varchar metadata_id FK
      varchar event_type
    }
    subscription_notification {
      varchar notification_id PK
      varchar subscription_id FK
      varchar event_id FK
      varchar status
    }
    drift_record {
      varchar drift_id PK
      varchar metadata_id FK
      varchar consumer_id FK
      varchar drift_type
    }

    metadata ||--o{ metadata_field : has
    metadata ||--o{ metadata_binding : binds
    metadata ||--o{ lineage_edge : source
    metadata ||--o{ lineage_edge : target
    metadata ||--o{ subscription : subscribed
    consumer ||--o{ subscription : declares
    consumer ||--o{ query_record : executes
    subscription ||--o{ query_record : audits
    metadata ||--o{ metadata_event : emits
    metadata_event ||--o{ subscription_notification : creates
    subscription ||--o{ subscription_notification : receives
    metadata ||--o{ drift_record : involved
```

## 4. 运行时序视图

### 4.1 启动时微服务元数据快照同步

```mermaid
sequenceDiagram
    participant App as Microservice
    participant SDK as Java SDK
    participant Server as Governance Service
    participant DB as GaussDB

    App->>SDK: ApplicationReadyEvent
    SDK->>SDK: assemble service metadata snapshot
    SDK->>Server: POST /rest/oss/inner/modelengineservice/v1/metadata/register
    Server->>DB: upsert metadata in service scope
    Server->>DB: soft remove missing metadata in scope
    DB-->>Server: sync result
    Server-->>SDK: metadataId mapping
```

### 4.2 订阅声明

```mermaid
sequenceDiagram
    participant App as Consumer App
    participant SDK as Java SDK
    participant Server as Governance Service
    participant DB as GaussDB

    App->>SDK: declare subscription
    SDK->>Server: POST /rest/oss/inner/modelengineservice/v1/subscriptions/{metadataId}
    Server->>DB: upsert consumer
    Server->>DB: upsert subscription
    Server-->>SDK: subscriptionId
```

### 4.3 产品 API 查询

```mermaid
sequenceDiagram
    participant App as Consumer App
    participant Server as Governance Service
    participant DB as GaussDB
    participant SR as StarRocks

    App->>Server: POST /rest/oss/inner/modelengineservice/v1/apiquery/{metadataId}
    Server->>DB: load metadata, schema, binding, subscription
    Server->>SR: execute read query
    SR-->>Server: rows
    Server->>DB: insert query_record
    Server-->>App: QueryResult
```

### 4.4 SQL Gateway 查询

```mermaid
sequenceDiagram
    participant App as Consumer App
    participant Server as Governance Service
    participant DB as GaussDB
    participant SR as StarRocks

    App->>Server: POST /rest/oss/inner/modelengineservice/v1/sqlquery
    Server->>Server: parse and validate read-only SQL
    Server->>DB: resolve registered metadata bindings
    Server->>SR: execute rewritten SQL
    SR-->>Server: rows
    Server->>DB: insert query_record
    Server-->>App: QueryResult
```

### 4.5 元数据事件通知

```mermaid
sequenceDiagram
    participant Caller as Runtime Caller
    participant Server as Governance Service
    participant DB as GaussDB
    participant Kafka as Kafka
    participant SDK as Consumer SDK

    Caller->>Server: PATCH / DELETE metadata
    Server->>DB: update metadata and insert metadata_event
    Server->>DB: match ACTIVE subscriptions
    Server->>DB: insert subscription_notification
    Server->>Kafka: publish data-gov.subscription-notifications
    Kafka-->>SDK: consume notification
    SDK-->>SDK: invoke business callback
```

## 5. 技术视图

```mermaid
flowchart TB
    subgraph Clients
      Micro[Java Microservices]
      Flink[Flink Jobs]
      Spark[Spark SQL / Spark Jobs]
    end

    subgraph SDK
      JavaSDK[DataGov Java SDK]
      Listener[Kafka Notification Listener]
    end

    subgraph Service
      Spring[Spring Boot Governance Service]
      Api[REST API]
      Gateway[StarRocks Query Gateway]
      Drift[Drift Analyzer]
    end

    subgraph Storage
      Gauss[GaussDB]
      Kafka[Kafka]
      StarRocks[StarRocks]
      Hive[Hive]
      Iceberg[Iceberg]
    end

    Micro --> JavaSDK
    Flink --> JavaSDK
    Spark --> JavaSDK
    JavaSDK --> Api
    Listener --> Kafka
    Api --> Spring
    Spring --> Gauss
    Spring --> Kafka
    Spring --> Gateway
    Gateway --> StarRocks
    StarRocks --> Hive
    StarRocks --> Iceberg
    StarRocks --> Gauss
    Drift --> Gauss
```

## 6. 部署视图

```mermaid
flowchart LR
    subgraph Project[data-gov]
      Backend[Spring Boot Governance Service]
      Frontend[Frontend]
      SDK[Java SDK Artifact]
    end

    subgraph SharedInfra[../shared-data-infra]
      GaussDB[GaussDB]
      Kafka[Kafka]
      StarRocks[StarRocks]
      Hive[Hive Metastore / HiveServer2]
      Spark[Spark / YARN]
      Monitor[Prometheus / Grafana]
    end

    Backend --> GaussDB
    Backend --> Kafka
    Backend --> StarRocks
    Backend --> Monitor
    StarRocks --> Hive
    StarRocks --> GaussDB
    SDK --> Backend
    SDK --> Kafka
```

部署约束：

- 本工程本地只保留 backend、frontend 和应用数据卷。
- GaussDB、Hive、HDFS/YARN、Kafka、StarRocks、Spark、Prometheus、Grafana 等基础能力复用 `../shared-data-infra`。
- 基础设施修改前必须检查 `../shared-data-infra` 是否已有同类服务或 profile。
