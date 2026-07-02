# 数据治理架构视图

本文使用 PlantUML 描述数据治理平台的用例视图、逻辑视图、数据模型视图、运行时序视图、技术视图和部署视图。

## 1. 用例视图

```plantuml
@startuml
left to right direction
actor "数据生产方微服务 / Flink / Spark" as Producer
actor "数据消费者微服务 / 分析服务" as Consumer
actor "治理管理员" as Admin
actor "Java SDK" as SDK

rectangle "数据治理平台" as Platform {
  usecase "启动时元数据快照同步" as Register
  usecase "声明订阅" as Subscribe
  usecase "监听变化通知" as Notify
  usecase "产品 API 查询" as ApiQuery
  usecase "SQL Gateway 查询" as SqlQuery
  usecase "元数据发现" as Discover
  usecase "血缘查询" as Lineage
  usecase "运行时修改 / 取消注册" as RuntimeChange
}

Producer --> SDK
Consumer --> SDK
SDK --> Register
SDK --> Subscribe
SDK --> Notify
Consumer --> ApiQuery
Consumer --> SqlQuery
Admin --> Discover
Admin --> Lineage
Admin --> RuntimeChange
@enduml
```

## 2. 逻辑视图

```plantuml
@startuml
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
@enduml
```

职责说明：

- `MetadataService` 负责启动快照同步、运行时修改、运行时取消注册、字段、物理绑定和事件生成。
- `LineageService` 负责表级和字段级血缘维护与查询。
- `SubscriptionService` 负责订阅声明、查询和取消。
- `QueryService` 负责产品 API 查询、SQL Gateway 查询和 `query_record` 写入。
- `NotificationService` 将 `metadata_event` 转换为订阅通知并发送 Kafka。
- `DriftService` 分析声明态和运行态差异。

## 3. 数据模型视图

```plantuml
@startuml
entity metadata {
  * metadata_id : varchar <<PK>>
  --
  asset_code : varchar <<UK>>
  metadata_type : varchar
  service_name : varchar
  environment : varchar
  status : varchar
}
entity metadata_field {
  * field_id : varchar <<PK>>
  metadata_id : varchar <<FK>>
  field_name : varchar
  field_type : varchar
}
entity metadata_binding {
  * binding_id : varchar <<PK>>
  metadata_id : varchar <<FK>>
  source_type : varchar
  qualified_name : varchar
}
entity lineage_edge {
  * lineage_id : varchar <<PK>>
  source_metadata_id : varchar <<FK>>
  target_metadata_id : varchar <<FK>>
  lineage_type : varchar
}
entity consumer {
  * consumer_id : varchar <<PK>>
  consumer_name : varchar
  consumer_type : varchar
  environment : varchar
}
entity subscription {
  * subscription_id : varchar <<PK>>
  metadata_id : varchar <<FK>>
  consumer_id : varchar <<FK>>
  usage_mode : varchar
  status : varchar
}
entity query_record {
  * query_record_id : varchar <<PK>>
  consumer_id : varchar <<FK>>
  subscription_id : varchar <<FK>>
  referenced_asset_codes : jsonb
}
entity metadata_event {
  * event_id : varchar <<PK>>
  metadata_id : varchar <<FK>>
  event_type : varchar
}
entity subscription_notification {
  * notification_id : varchar <<PK>>
  subscription_id : varchar <<FK>>
  event_id : varchar <<FK>>
  status : varchar
}
entity drift_record {
  * drift_id : varchar <<PK>>
  metadata_id : varchar <<FK>>
  consumer_id : varchar <<FK>>
  drift_type : varchar
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
@enduml
```

## 4. 运行时序视图

### 4.1 启动时微服务元数据快照同步

```plantuml
@startuml
participant App as Microservice
participant SDK as "Java SDK"
participant Server as "Governance Service"
database DB as GaussDB

App -> SDK : ApplicationReadyEvent
SDK -> SDK : assemble service metadata snapshot
SDK -> Server : POST /rest/oss/inner/modelengineservice/v1/metadata/register
Server -> DB : upsert metadata in service scope
Server -> DB : soft remove missing metadata in scope
DB --> Server : sync result
Server --> SDK : metadataId mapping
@enduml
```

### 4.2 订阅声明

```plantuml
@startuml
participant App as "Consumer App"
participant SDK as "Java SDK"
participant Server as "Governance Service"
database DB as GaussDB

App -> SDK : declare subscription
SDK -> Server : POST /rest/oss/inner/modelengineservice/v1/subscriptions/{metadataId}
Server -> DB : upsert consumer
Server -> DB : upsert subscription
Server --> SDK : subscriptionId
@enduml
```

### 4.3 产品 API 查询

```plantuml
@startuml
participant App as "Consumer App"
participant Server as "Governance Service"
database DB as GaussDB
database SR as StarRocks

App -> Server : POST /rest/oss/inner/modelengineservice/v1/apiquery/{metadataId}
Server -> DB : load metadata, schema, binding, subscription
Server -> SR : execute read query
SR --> Server : rows
Server -> DB : insert query_record
Server --> App : QueryResult
@enduml
```

### 4.4 SQL Gateway 查询

```plantuml
@startuml
participant App as "Consumer App"
participant Server as "Governance Service"
database DB as GaussDB
database SR as StarRocks

App -> Server : POST /rest/oss/inner/modelengineservice/v1/sqlquery
Server -> Server : parse and validate read-only SQL
Server -> DB : resolve registered metadata bindings
Server -> SR : execute rewritten SQL
SR --> Server : rows
Server -> DB : insert query_record
Server --> App : QueryResult
@enduml
```

### 4.5 元数据事件通知

```plantuml
@startuml
participant Caller as "Runtime Caller"
participant Server as "Governance Service"
database DB as GaussDB
queue Kafka
participant SDK as "Consumer SDK"

Caller -> Server : PATCH / DELETE metadata
Server -> DB : update metadata and insert metadata_event
Server -> DB : match ACTIVE subscriptions
Server -> DB : insert subscription_notification
Server -> Kafka : publish data-gov.subscription-notifications
Kafka --> SDK : consume notification
SDK -> SDK : invoke business callback
@enduml
```

## 5. 技术视图

```plantuml
@startuml
skinparam componentStyle rectangle
package Clients {
  component "Java Microservices" as Micro
  component "Flink Jobs" as Flink
  component "Spark SQL / Spark Jobs" as Spark
}
package SDK {
  component "DataGov Java SDK" as JavaSDK
  component "Kafka Notification Listener" as Listener
}
package Service {
  component "Spring Boot Governance Service" as Spring
  component "REST API" as Api
  component "StarRocks Query Gateway" as Gateway
  component "Drift Analyzer" as Drift
}
package Storage {
  database GaussDB as Gauss
  queue Kafka
  database StarRocks
  database Hive
  database Iceberg
}

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
@enduml
```

## 6. 部署视图

```plantuml
@startuml
left to right direction
node "data-gov" as Project {
  component "Spring Boot Governance Service" as Backend
  component Frontend
  artifact "Java SDK Artifact" as SDK
}
node "../shared-data-infra" as SharedInfra {
  database GaussDB
  queue Kafka
  database StarRocks
  database "Hive Metastore / HiveServer2" as Hive
  node "Spark / YARN" as Spark
  component "Prometheus / Grafana" as Monitor
}

Backend --> GaussDB
Backend --> Kafka
Backend --> StarRocks
Backend --> Monitor
StarRocks --> Hive
StarRocks --> GaussDB
SDK --> Backend
SDK --> Kafka
@enduml
```

部署约束：

- 本工程本地只保留 backend、frontend 和应用数据卷。
- GaussDB、Hive、HDFS/YARN、Kafka、StarRocks、Spark、Prometheus、Grafana 等基础能力复用 `../shared-data-infra`。
- 基础设施修改前必须检查 `../shared-data-infra` 是否已有同类服务或 profile。
