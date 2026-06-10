# Subscription and SDK Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the next independently testable Java governance slice: subscription declaration APIs, SDK startup registration APIs, and Flink/Spark job declaration registration without job run lifecycle tracking.

**Architecture:** Extend the existing `data-gov-platform` modules. `data-gov-common` owns shared enums and DTOs, `data-gov-server` persists consumers/subscriptions/jobs in GaussDB-compatible tables and exposes REST endpoints, and `data-gov-sdk` provides a small Java client plus Spring Boot auto-registration. This slice does not implement Kafka notification publishing, StarRocks query execution, lineage APIs, or drift detection.

**Tech Stack:** Java 17, Spring Boot 3.3.x, Maven, Flyway, JDBC, H2 tests, MockMvc, Spring `RestClient`, Spring Boot auto-configuration tests.

---

## Scope Notes

This plan continues after `docs/superpowers/plans/2026-06-10-java-governance-foundation.md` and assumes the current asset catalog APIs already exist.

Implement in this slice:

- `consumer`, `subscription`, and `consumer_job` tables.
- Server SDK endpoints:
  - `POST /api/sdk/subscriptions/register`
  - `POST /api/sdk/jobs/register`
- Product-facing subscription endpoints:
  - `POST /api/assets/{assetCode}/subscriptions`
  - `GET /api/subscriptions`
  - `GET /api/subscriptions/{subscriptionId}`
  - `PATCH /api/subscriptions/{subscriptionId}`
- Java SDK core client for startup subscription registration and job declaration registration.
- Spring Boot SDK auto-configuration for microservice startup registration.

Do not implement in this slice:

- `POST /api/sdk/jobs/{jobId}/runs/start`
- `POST /api/sdk/jobs/{jobId}/runs/{runId}/finish`
- `GET /api/notifications`
- `PATCH /api/notifications/{notificationId}/ack`
- Kafka notification publishing/listening.
- Automatic `lineage_edge` creation from job completion.

## File Structure

Create:

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/ConsumerType.java`  
  Consumer type enum used by server and SDK.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/UsageMode.java`  
  Subscription usage mode enum.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/SubscriptionSourceType.java`  
  Source of subscription declarations.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/SubscriptionStatus.java`  
  Subscription status enum.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/JobType.java`  
  Flink/Spark job type enum.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/JobStatus.java`  
  Job declaration status enum.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/AssetEventType.java`  
  Notification preference enum used by subscription declarations.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/GovernanceDtos.java`  
  DTO records for consumer, subscription, SDK registration, and job registration.

- `data-gov-platform/data-gov-server/src/main/resources/db/migration/V2__subscription_and_job_declarations.sql`  
  Flyway migration for consumer/subscription/job declaration tables.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionRepository.java`  
  JDBC repository for consumers, subscriptions, and job declarations.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionService.java`  
  Business service for upsert semantics and asset resolution.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionNotFoundException.java`  
  Explicit 404 exception for subscription lookup failures.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionController.java`  
  Product-facing subscription REST endpoints.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/sdk/SdkController.java`  
  SDK-only REST endpoints.

- `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/subscription/SubscriptionControllerTest.java`  
  MockMvc tests for product-facing subscription endpoints.

- `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/sdk/SdkRegistrationControllerTest.java`  
  MockMvc tests for SDK startup and job registration.

- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DataGovClient.java`  
  Java SDK client interface.

- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DefaultDataGovClient.java`  
  RestClient-backed SDK implementation.

- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DataGovClientException.java`  
  SDK client exception.

- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovProperties.java`  
  Spring Boot configuration properties.

- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovAutoConfiguration.java`  
  Auto-configuration that registers a `DataGovClient`.

- `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovStartupRegistrar.java`  
  `ApplicationReadyEvent` listener that registers configured subscriptions.

- `data-gov-platform/data-gov-sdk/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`  
  Spring Boot 3 auto-configuration entry.

- `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/DefaultDataGovClientTest.java`  
  SDK HTTP client tests.

- `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/spring/DataGovAutoConfigurationTest.java`  
  Spring Boot auto-configuration tests.

Modify:

- `data-gov-platform/data-gov-sdk/pom.xml`  
  Add Spring Web, Boot auto-configuration, Jackson, and test dependencies.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`  
  Map unknown asset/subscription errors to explicit JSON errors.

---

### Task 1: Shared Governance Enums and DTOs

**Files:**
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/ConsumerType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/UsageMode.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/SubscriptionSourceType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/SubscriptionStatus.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/JobType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/JobStatus.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/AssetEventType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/GovernanceDtos.java`

- [ ] **Step 1: Add governance enums**

Create `ConsumerType.java`:

```java
package io.datagov.common.enums;

public enum ConsumerType {
    MICROSERVICE,
    FLINK_JOB,
    SPARK_JOB,
    USER,
    BI
}
```

Create `UsageMode.java`:

```java
package io.datagov.common.enums;

public enum UsageMode {
    API_QUERY,
    SQL_QUERY,
    FLINK_CONSUME,
    SPARK_CONSUME,
    MICROSERVICE_READ,
    KAFKA_CONSUME
}
```

Create `SubscriptionSourceType.java`:

```java
package io.datagov.common.enums;

public enum SubscriptionSourceType {
    SDK_STARTUP,
    API,
    RUNTIME_REPORT,
    INFERRED
}
```

Create `SubscriptionStatus.java`:

```java
package io.datagov.common.enums;

public enum SubscriptionStatus {
    ACTIVE,
    STALE,
    PAUSED,
    REVOKED
}
```

Create `JobType.java`:

```java
package io.datagov.common.enums;

public enum JobType {
    FLINK,
    SPARK
}
```

Create `JobStatus.java`:

```java
package io.datagov.common.enums;

public enum JobStatus {
    ACTIVE,
    PAUSED,
    OFFLINE
}
```

Create `AssetEventType.java`:

```java
package io.datagov.common.enums;

public enum AssetEventType {
    SCHEMA_CHANGE,
    DEPRECATION,
    OFFLINE,
    DATA_QUALITY_ALERT,
    REFRESH_DELAY,
    LINEAGE_CHANGE
}
```

- [ ] **Step 2: Add governance DTOs**

Create `GovernanceDtos.java`:

```java
package io.datagov.common.dto;

import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.JobStatus;
import io.datagov.common.enums.JobType;
import io.datagov.common.enums.SubscriptionSourceType;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.common.enums.UsageMode;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class GovernanceDtos {
    private GovernanceDtos() {
    }

    public record ConsumerRequest(
            @NotBlank String consumerName,
            @NotNull ConsumerType consumerType,
            String owner,
            String environment,
            String runtimeVersion,
            String instanceId
    ) {
    }

    public record ConsumerResponse(
            String consumerId,
            ConsumerType consumerType,
            String consumerName,
            String owner,
            String environment,
            String runtimeVersion,
            String instanceId,
            String declarationHash,
            Instant lastRegisteredAt,
            Instant lastSeenAt
    ) {
    }

    public record SubscriptionDeclarationRequest(
            @NotBlank String assetCode,
            @NotNull UsageMode usageMode,
            String purpose,
            List<String> fields,
            List<AssetEventType> notifyOn
    ) {
    }

    public record CreateSubscriptionRequest(
            @Valid @NotNull ConsumerRequest consumer,
            @Valid @NotNull SubscriptionDeclarationRequest subscription
    ) {
    }

    public record UpdateSubscriptionRequest(
            UsageMode usageMode,
            String purpose,
            List<String> fields,
            List<AssetEventType> notifyOn,
            SubscriptionStatus status
    ) {
    }

    public record SubscriptionResponse(
            String subscriptionId,
            String assetId,
            String assetCode,
            String consumerId,
            String consumerName,
            UsageMode usageMode,
            String purpose,
            List<String> declaredFields,
            List<AssetEventType> notifyOn,
            SubscriptionSourceType sourceType,
            SubscriptionStatus status,
            String declarationHash,
            Instant lastRegisteredAt,
            Instant lastRuntimeSeenAt,
            Instant createdAt,
            Instant updatedAt
    ) {
    }

    public record SdkSubscriptionRegistrationRequest(
            @Valid @NotNull ConsumerRequest consumer,
            String declarationHash,
            @Valid @NotEmpty List<SubscriptionDeclarationRequest> subscriptions
    ) {
    }

    public record SdkSubscriptionRegistrationResponse(
            ConsumerResponse consumer,
            List<SubscriptionResponse> subscriptions,
            Map<String, String> assetCodeToSubscriptionId
    ) {
    }

    public record JobRegistrationRequest(
            @Valid @NotNull ConsumerRequest consumer,
            @NotBlank String jobName,
            @NotNull JobType jobType,
            String owner,
            String codeRef,
            Map<String, Object> runtimeConfig,
            List<String> inputAssets,
            List<String> outputAssets,
            String declarationHash,
            @Valid List<SubscriptionDeclarationRequest> subscriptions
    ) {
    }

    public record JobRegistrationResponse(
            String jobId,
            String jobName,
            JobType jobType,
            JobStatus status,
            ConsumerResponse consumer,
            List<SubscriptionResponse> subscriptions,
            Instant lastRegisteredAt
    ) {
    }
}
```

- [ ] **Step 3: Compile common module**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-common test
```

Expected: `BUILD SUCCESS`.

- [ ] **Step 4: Commit**

```bash
git add data-gov-platform/data-gov-common/src/main/java/io/datagov/common
git commit -m "feat: add governance registration DTOs"
```

---

### Task 2: GaussDB Tables for Consumers, Subscriptions, and Job Declarations

**Files:**
- Create: `data-gov-platform/data-gov-server/src/main/resources/db/migration/V2__subscription_and_job_declarations.sql`

- [ ] **Step 1: Add Flyway migration**

Create `V2__subscription_and_job_declarations.sql`:

```sql
create table consumer (
    consumer_id varchar(64) primary key,
    consumer_type varchar(32) not null,
    consumer_name varchar(128) not null,
    owner varchar(128),
    environment varchar(64) not null default 'default',
    runtime_version varchar(128),
    instance_id varchar(256),
    declaration_hash varchar(128),
    last_registered_at timestamp,
    last_seen_at timestamp,
    created_at timestamp not null,
    updated_at timestamp not null,
    constraint uk_consumer_name_env unique(consumer_name, environment)
);

create index idx_consumer_type on consumer(consumer_type);
create index idx_consumer_last_registered_at on consumer(last_registered_at);

create table subscription (
    subscription_id varchar(64) primary key,
    asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    consumer_id varchar(64) not null references consumer(consumer_id) on delete cascade,
    usage_mode varchar(32) not null,
    purpose text,
    declared_fields text,
    notify_on text,
    source_type varchar(32) not null,
    declaration_hash varchar(128),
    last_registered_at timestamp,
    last_runtime_seen_at timestamp,
    status varchar(32) not null,
    created_at timestamp not null,
    updated_at timestamp not null,
    constraint uk_subscription_asset_consumer_usage unique(asset_id, consumer_id, usage_mode)
);

create index idx_subscription_asset_id on subscription(asset_id);
create index idx_subscription_consumer_id on subscription(consumer_id);
create index idx_subscription_status on subscription(status);

create table consumer_job (
    job_id varchar(64) primary key,
    consumer_id varchar(64) not null references consumer(consumer_id) on delete cascade,
    job_name varchar(128) not null,
    job_type varchar(32) not null,
    owner varchar(128),
    code_ref text,
    runtime_config text,
    input_asset_codes text,
    output_asset_codes text,
    declaration_hash varchar(128),
    status varchar(32) not null,
    last_registered_at timestamp,
    created_at timestamp not null,
    updated_at timestamp not null,
    constraint uk_consumer_job_name_type unique(consumer_id, job_name, job_type)
);

create index idx_consumer_job_consumer_id on consumer_job(consumer_id);
create index idx_consumer_job_name on consumer_job(job_name);
```

Use `text` for list/map JSON payloads in this slice, matching `asset_physical_binding.properties` from `V1__core_asset_catalog.sql`.

- [ ] **Step 2: Verify migrations apply**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-server -am test
```

Expected: `BUILD SUCCESS`; existing `AssetControllerTest` still passes with V1 and V2 migrations.

- [ ] **Step 3: Commit**

```bash
git add data-gov-platform/data-gov-server/src/main/resources/db/migration/V2__subscription_and_job_declarations.sql
git commit -m "feat: add subscription declaration schema"
```

---

### Task 3: Server Subscription and SDK Registration APIs

**Files:**
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionRepository.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionService.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionNotFoundException.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/subscription/SubscriptionController.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/sdk/SdkController.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/subscription/SubscriptionControllerTest.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/sdk/SdkRegistrationControllerTest.java`
- Modify: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`

- [ ] **Step 1: Write failing subscription API tests**

Create `SubscriptionControllerTest.java`:

```java
package io.datagov.server.subscription;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class SubscriptionControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @BeforeEach
    void registerAsset() throws Exception {
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "ads_cell_profile",
                                  "assetName": "ADS Cell Profile",
                                  "assetType": "TABLE",
                                  "engine": "STARROCKS",
                                  "lifecycleStatus": "ACTIVE",
                                  "queryable": true,
                                  "fields": [
                                    {"fieldName": "cell_id", "fieldType": "varchar", "ordinalPosition": 1},
                                    {"fieldName": "coverage_score", "fieldType": "double", "ordinalPosition": 2}
                                  ]
                                }
                                """))
                .andExpect(status().isOk());
    }

    @Test
    void createListGetAndPatchSubscription() throws Exception {
        String createResponse = mockMvc.perform(post("/api/assets/ads_cell_profile/subscriptions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "owner": "network-team",
                                    "environment": "prod",
                                    "runtimeVersion": "1.8.3",
                                    "instanceId": "pod-1"
                                  },
                                  "subscription": {
                                    "assetCode": "ads_cell_profile",
                                    "usageMode": "API_QUERY",
                                    "purpose": "dashboard display",
                                    "fields": ["cell_id", "coverage_score"],
                                    "notifyOn": ["SCHEMA_CHANGE", "DEPRECATION"]
                                  }
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.usageMode").value("API_QUERY"))
                .andExpect(jsonPath("$.declaredFields", hasSize(2)))
                .andExpect(jsonPath("$.notifyOn", hasSize(2)))
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andReturn()
                .getResponse()
                .getContentAsString();

        String subscriptionId = com.jayway.jsonpath.JsonPath.read(createResponse, "$.subscriptionId");

        mockMvc.perform(get("/api/subscriptions"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.subscriptionId == '" + subscriptionId + "')]", hasSize(1)));

        mockMvc.perform(get("/api/subscriptions/" + subscriptionId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.subscriptionId").value(subscriptionId))
                .andExpect(jsonPath("$.purpose").value("dashboard display"));

        mockMvc.perform(patch("/api/subscriptions/" + subscriptionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "purpose": "dashboard display v2",
                                  "fields": ["cell_id"],
                                  "notifyOn": ["SCHEMA_CHANGE"],
                                  "status": "PAUSED"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.purpose").value("dashboard display v2"))
                .andExpect(jsonPath("$.declaredFields", hasSize(1)))
                .andExpect(jsonPath("$.status").value("PAUSED"));
    }

    @Test
    void subscribingMissingAssetReturns404() throws Exception {
        mockMvc.perform(post("/api/assets/missing_asset/subscriptions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "environment": "prod"
                                  },
                                  "subscription": {
                                    "assetCode": "missing_asset",
                                    "usageMode": "API_QUERY"
                                  }
                                }
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
    }
}
```

- [ ] **Step 2: Write failing SDK registration tests**

Create `SdkRegistrationControllerTest.java`:

```java
package io.datagov.server.sdk;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class SdkRegistrationControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @BeforeEach
    void registerAssets() throws Exception {
        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "ods_ue_signal",
                                  "assetType": "STREAM",
                                  "engine": "KAFKA",
                                  "fields": [{"fieldName": "ue_id", "fieldType": "string"}]
                                }
                                """))
                .andExpect(status().isOk());

        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "assetCode": "dwd_session_qos",
                                  "assetType": "TABLE",
                                  "engine": "HIVE",
                                  "fields": [{"fieldName": "session_id", "fieldType": "string"}]
                                }
                                """))
                .andExpect(status().isOk());
    }

    @Test
    void sdkRegistersSubscriptionsAtStartup() throws Exception {
        mockMvc.perform(post("/api/sdk/subscriptions/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "rno-dashboard",
                                    "consumerType": "MICROSERVICE",
                                    "owner": "network-team",
                                    "environment": "prod",
                                    "runtimeVersion": "1.8.3",
                                    "instanceId": "pod-1"
                                  },
                                  "declarationHash": "sha256:abc",
                                  "subscriptions": [
                                    {
                                      "assetCode": "dwd_session_qos",
                                      "usageMode": "API_QUERY",
                                      "purpose": "dashboard read",
                                      "fields": ["session_id"],
                                      "notifyOn": ["SCHEMA_CHANGE"]
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.consumer.consumerName").value("rno-dashboard"))
                .andExpect(jsonPath("$.subscriptions", hasSize(1)))
                .andExpect(jsonPath("$.subscriptions[0].assetCode").value("dwd_session_qos"))
                .andExpect(jsonPath("$.assetCodeToSubscriptionId.dwd_session_qos").exists());
    }

    @Test
    void sdkRegistersFlinkJobDeclarationWithoutRunLifecycle() throws Exception {
        mockMvc.perform(post("/api/sdk/jobs/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "consumer": {
                                    "consumerName": "cell-hourly-agg",
                                    "consumerType": "FLINK_JOB",
                                    "owner": "network-team",
                                    "environment": "prod"
                                  },
                                  "jobName": "cell-hourly-agg",
                                  "jobType": "FLINK",
                                  "owner": "network-team",
                                  "codeRef": "git://repo/jobs/cell-hourly-agg",
                                  "inputAssets": ["ods_ue_signal"],
                                  "outputAssets": ["dwd_session_qos"],
                                  "declarationHash": "sha256:jobabc",
                                  "subscriptions": [
                                    {
                                      "assetCode": "ods_ue_signal",
                                      "usageMode": "FLINK_CONSUME",
                                      "purpose": "hourly qos aggregation",
                                      "fields": ["ue_id"],
                                      "notifyOn": ["SCHEMA_CHANGE", "DEPRECATION"]
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.jobName").value("cell-hourly-agg"))
                .andExpect(jsonPath("$.jobType").value("FLINK"))
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andExpect(jsonPath("$.subscriptions", hasSize(1)));
    }
}
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=SubscriptionControllerTest,SdkRegistrationControllerTest test
```

Expected: FAIL because the new controllers and repository do not exist.

- [ ] **Step 4: Implement repository**

Create `SubscriptionRepository.java` with these public methods and JSON helpers:

```java
package io.datagov.server.subscription;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.enums.AssetEventType;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.JobStatus;
import io.datagov.common.enums.JobType;
import io.datagov.common.enums.SubscriptionSourceType;
import io.datagov.common.enums.SubscriptionStatus;
import io.datagov.common.enums.UsageMode;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public class SubscriptionRepository {
    private static final TypeReference<List<String>> STRING_LIST = new TypeReference<>() {
    };
    private static final TypeReference<List<AssetEventType>> EVENT_LIST = new TypeReference<>() {
    };
    private static final TypeReference<Map<String, Object>> OBJECT_MAP = new TypeReference<>() {
    };

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public SubscriptionRepository(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public Optional<String> findAssetId(String assetCode) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject(
                    "select asset_id from data_asset where asset_code = ?",
                    String.class,
                    assetCode));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    public GovernanceDtos.ConsumerResponse upsertConsumer(
            GovernanceDtos.ConsumerRequest request,
            String declarationHash,
            Instant now
    ) {
        String environment = normalizeEnvironment(request.environment());
        Optional<GovernanceDtos.ConsumerResponse> existing = findConsumer(request.consumerName(), environment);
        if (existing.isEmpty()) {
            String consumerId = "consumer_" + java.util.UUID.randomUUID();
            jdbcTemplate.update("""
                    insert into consumer(
                      consumer_id, consumer_type, consumer_name, owner, environment, runtime_version, instance_id,
                      declaration_hash, last_registered_at, last_seen_at, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    consumerId, request.consumerType().name(), request.consumerName(), request.owner(), environment,
                    request.runtimeVersion(), request.instanceId(), declarationHash, Timestamp.from(now),
                    Timestamp.from(now), Timestamp.from(now), Timestamp.from(now));
            return findConsumer(request.consumerName(), environment).orElseThrow();
        }

        jdbcTemplate.update("""
                update consumer
                set consumer_type = ?, owner = ?, runtime_version = ?, instance_id = ?, declaration_hash = ?,
                    last_registered_at = ?, last_seen_at = ?, updated_at = ?
                where consumer_id = ?
                """,
                request.consumerType().name(), request.owner(), request.runtimeVersion(), request.instanceId(),
                declarationHash, Timestamp.from(now), Timestamp.from(now), Timestamp.from(now),
                existing.get().consumerId());
        return findConsumer(request.consumerName(), environment).orElseThrow();
    }

    public Optional<GovernanceDtos.ConsumerResponse> findConsumer(String consumerName, String environment) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select consumer_id, consumer_type, consumer_name, owner, environment, runtime_version, instance_id,
                           declaration_hash, last_registered_at, last_seen_at
                    from consumer
                    where consumer_name = ? and environment = ?
                    """, consumerMapper(), consumerName, normalizeEnvironment(environment)));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    public GovernanceDtos.SubscriptionResponse upsertSubscription(
            String assetId,
            String assetCode,
            GovernanceDtos.ConsumerResponse consumer,
            GovernanceDtos.SubscriptionDeclarationRequest declaration,
            SubscriptionSourceType sourceType,
            String declarationHash,
            Instant now
    ) {
        Optional<String> existingId = findSubscriptionId(assetId, consumer.consumerId(), declaration.usageMode());
        if (existingId.isEmpty()) {
            String subscriptionId = "sub_" + java.util.UUID.randomUUID();
            jdbcTemplate.update("""
                    insert into subscription(
                      subscription_id, asset_id, consumer_id, usage_mode, purpose, declared_fields, notify_on,
                      source_type, declaration_hash, last_registered_at, status, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    subscriptionId, assetId, consumer.consumerId(), declaration.usageMode().name(), declaration.purpose(),
                    writeJson(defaultList(declaration.fields())), writeJson(defaultEvents(declaration.notifyOn())),
                    sourceType.name(), declarationHash, Timestamp.from(now), SubscriptionStatus.ACTIVE.name(),
                    Timestamp.from(now), Timestamp.from(now));
            return findSubscription(subscriptionId).orElseThrow();
        }

        jdbcTemplate.update("""
                update subscription
                set purpose = ?, declared_fields = ?, notify_on = ?, source_type = ?, declaration_hash = ?,
                    last_registered_at = ?, status = ?, updated_at = ?
                where subscription_id = ?
                """,
                declaration.purpose(), writeJson(defaultList(declaration.fields())),
                writeJson(defaultEvents(declaration.notifyOn())), sourceType.name(), declarationHash,
                Timestamp.from(now), SubscriptionStatus.ACTIVE.name(), Timestamp.from(now), existingId.get());
        return findSubscription(existingId.get()).orElseThrow();
    }

    public List<GovernanceDtos.SubscriptionResponse> listSubscriptions() {
        return jdbcTemplate.query(subscriptionSelect() + " order by s.updated_at desc", subscriptionMapper());
    }

    public Optional<GovernanceDtos.SubscriptionResponse> findSubscription(String subscriptionId) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject(
                    subscriptionSelect() + " where s.subscription_id = ?",
                    subscriptionMapper(),
                    subscriptionId));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    public GovernanceDtos.SubscriptionResponse updateSubscription(
            String subscriptionId,
            GovernanceDtos.UpdateSubscriptionRequest request,
            Instant now
    ) {
        GovernanceDtos.SubscriptionResponse current = findSubscription(subscriptionId)
                .orElseThrow(() -> new SubscriptionNotFoundException(subscriptionId));
        UsageMode usageMode = request.usageMode() == null ? current.usageMode() : request.usageMode();
        SubscriptionStatus status = request.status() == null ? current.status() : request.status();
        String purpose = request.purpose() == null ? current.purpose() : request.purpose();
        List<String> fields = request.fields() == null ? current.declaredFields() : request.fields();
        List<AssetEventType> notifyOn = request.notifyOn() == null ? current.notifyOn() : request.notifyOn();

        jdbcTemplate.update("""
                update subscription
                set usage_mode = ?, purpose = ?, declared_fields = ?, notify_on = ?, status = ?, updated_at = ?
                where subscription_id = ?
                """,
                usageMode.name(), purpose, writeJson(fields), writeJson(notifyOn), status.name(),
                Timestamp.from(now), subscriptionId);
        return findSubscription(subscriptionId).orElseThrow();
    }

    public GovernanceDtos.JobRegistrationResponse upsertJob(
            GovernanceDtos.ConsumerResponse consumer,
            GovernanceDtos.JobRegistrationRequest request,
            List<GovernanceDtos.SubscriptionResponse> subscriptions,
            Instant now
    ) {
        Optional<String> existingJobId = findJobId(consumer.consumerId(), request.jobName(), request.jobType());
        if (existingJobId.isEmpty()) {
            String jobId = "job_" + java.util.UUID.randomUUID();
            jdbcTemplate.update("""
                    insert into consumer_job(
                      job_id, consumer_id, job_name, job_type, owner, code_ref, runtime_config, input_asset_codes,
                      output_asset_codes, declaration_hash, status, last_registered_at, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    jobId, consumer.consumerId(), request.jobName(), request.jobType().name(), request.owner(),
                    request.codeRef(), writeJson(defaultMap(request.runtimeConfig())),
                    writeJson(defaultList(request.inputAssets())), writeJson(defaultList(request.outputAssets())),
                    request.declarationHash(), JobStatus.ACTIVE.name(), Timestamp.from(now), Timestamp.from(now),
                    Timestamp.from(now));
            return new GovernanceDtos.JobRegistrationResponse(
                    jobId, request.jobName(), request.jobType(), JobStatus.ACTIVE, consumer, subscriptions, now);
        }

        jdbcTemplate.update("""
                update consumer_job
                set owner = ?, code_ref = ?, runtime_config = ?, input_asset_codes = ?, output_asset_codes = ?,
                    declaration_hash = ?, status = ?, last_registered_at = ?, updated_at = ?
                where job_id = ?
                """,
                request.owner(), request.codeRef(), writeJson(defaultMap(request.runtimeConfig())),
                writeJson(defaultList(request.inputAssets())), writeJson(defaultList(request.outputAssets())),
                request.declarationHash(), JobStatus.ACTIVE.name(), Timestamp.from(now), Timestamp.from(now),
                existingJobId.get());
        return new GovernanceDtos.JobRegistrationResponse(
                existingJobId.get(), request.jobName(), request.jobType(), JobStatus.ACTIVE, consumer, subscriptions, now);
    }

    private Optional<String> findSubscriptionId(String assetId, String consumerId, UsageMode usageMode) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select subscription_id from subscription
                    where asset_id = ? and consumer_id = ? and usage_mode = ?
                    """, String.class, assetId, consumerId, usageMode.name()));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    private Optional<String> findJobId(String consumerId, String jobName, JobType jobType) {
        try {
            return Optional.ofNullable(jdbcTemplate.queryForObject("""
                    select job_id from consumer_job
                    where consumer_id = ? and job_name = ? and job_type = ?
                    """, String.class, consumerId, jobName, jobType.name()));
        } catch (EmptyResultDataAccessException ex) {
            return Optional.empty();
        }
    }

    private RowMapper<GovernanceDtos.ConsumerResponse> consumerMapper() {
        return (rs, rowNum) -> new GovernanceDtos.ConsumerResponse(
                rs.getString("consumer_id"),
                ConsumerType.valueOf(rs.getString("consumer_type")),
                rs.getString("consumer_name"),
                rs.getString("owner"),
                rs.getString("environment"),
                rs.getString("runtime_version"),
                rs.getString("instance_id"),
                rs.getString("declaration_hash"),
                toInstant(rs.getTimestamp("last_registered_at")),
                toInstant(rs.getTimestamp("last_seen_at")));
    }

    private String subscriptionSelect() {
        return """
                select s.subscription_id, s.asset_id, a.asset_code, s.consumer_id, c.consumer_name,
                       s.usage_mode, s.purpose, s.declared_fields, s.notify_on, s.source_type, s.status,
                       s.declaration_hash, s.last_registered_at, s.last_runtime_seen_at, s.created_at, s.updated_at
                from subscription s
                join data_asset a on a.asset_id = s.asset_id
                join consumer c on c.consumer_id = s.consumer_id
                """;
    }

    private RowMapper<GovernanceDtos.SubscriptionResponse> subscriptionMapper() {
        return (rs, rowNum) -> new GovernanceDtos.SubscriptionResponse(
                rs.getString("subscription_id"),
                rs.getString("asset_id"),
                rs.getString("asset_code"),
                rs.getString("consumer_id"),
                rs.getString("consumer_name"),
                UsageMode.valueOf(rs.getString("usage_mode")),
                rs.getString("purpose"),
                readJson(rs.getString("declared_fields"), STRING_LIST, List.of()),
                readJson(rs.getString("notify_on"), EVENT_LIST, List.of()),
                SubscriptionSourceType.valueOf(rs.getString("source_type")),
                SubscriptionStatus.valueOf(rs.getString("status")),
                rs.getString("declaration_hash"),
                toInstant(rs.getTimestamp("last_registered_at")),
                toInstant(rs.getTimestamp("last_runtime_seen_at")),
                toInstant(rs.getTimestamp("created_at")),
                toInstant(rs.getTimestamp("updated_at")));
    }

    private String normalizeEnvironment(String environment) {
        return environment == null || environment.isBlank() ? "default" : environment;
    }

    private List<String> defaultList(List<String> values) {
        return values == null ? List.of() : values;
    }

    private List<AssetEventType> defaultEvents(List<AssetEventType> values) {
        return values == null ? List.of() : values;
    }

    private Map<String, Object> defaultMap(Map<String, Object> values) {
        return values == null ? Map.of() : values;
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception ex) {
            return "[]";
        }
    }

    private <T> T readJson(String value, TypeReference<T> type, T fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        try {
            return objectMapper.readValue(value, type);
        } catch (Exception ex) {
            return fallback;
        }
    }

    private Instant toInstant(Timestamp timestamp) {
        return timestamp == null ? null : timestamp.toInstant();
    }
}
```

- [ ] **Step 5: Add subscription exception**

Create `SubscriptionNotFoundException.java`:

```java
package io.datagov.server.subscription;

public class SubscriptionNotFoundException extends RuntimeException {
    public SubscriptionNotFoundException(String subscriptionId) {
        super(subscriptionId);
    }
}
```

- [ ] **Step 6: Implement service**

Create `SubscriptionService.java`:

```java
package io.datagov.server.subscription;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.enums.SubscriptionSourceType;
import io.datagov.server.asset.AssetNotFoundException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class SubscriptionService {
    private final SubscriptionRepository repository;

    public SubscriptionService(SubscriptionRepository repository) {
        this.repository = repository;
    }

    @Transactional
    public GovernanceDtos.SubscriptionResponse createApiSubscription(
            String assetCode,
            GovernanceDtos.CreateSubscriptionRequest request
    ) {
        String assetId = repository.findAssetId(assetCode).orElseThrow(() -> new AssetNotFoundException(assetCode));
        GovernanceDtos.SubscriptionDeclarationRequest declaration = new GovernanceDtos.SubscriptionDeclarationRequest(
                assetCode,
                request.subscription().usageMode(),
                request.subscription().purpose(),
                request.subscription().fields(),
                request.subscription().notifyOn());
        Instant now = Instant.now();
        GovernanceDtos.ConsumerResponse consumer = repository.upsertConsumer(request.consumer(), null, now);
        return repository.upsertSubscription(assetId, assetCode, consumer, declaration, SubscriptionSourceType.API, null, now);
    }

    @Transactional
    public GovernanceDtos.SdkSubscriptionRegistrationResponse registerSdkSubscriptions(
            GovernanceDtos.SdkSubscriptionRegistrationRequest request
    ) {
        Instant now = Instant.now();
        GovernanceDtos.ConsumerResponse consumer = repository.upsertConsumer(
                request.consumer(), request.declarationHash(), now);
        List<GovernanceDtos.SubscriptionResponse> subscriptions = request.subscriptions().stream()
                .map(declaration -> registerOneSdkSubscription(consumer, declaration, request.declarationHash(), now))
                .toList();
        Map<String, String> mapping = new LinkedHashMap<>();
        for (GovernanceDtos.SubscriptionResponse subscription : subscriptions) {
            mapping.put(subscription.assetCode(), subscription.subscriptionId());
        }
        return new GovernanceDtos.SdkSubscriptionRegistrationResponse(consumer, subscriptions, mapping);
    }

    @Transactional
    public GovernanceDtos.JobRegistrationResponse registerJob(GovernanceDtos.JobRegistrationRequest request) {
        Instant now = Instant.now();
        GovernanceDtos.ConsumerResponse consumer = repository.upsertConsumer(
                request.consumer(), request.declarationHash(), now);
        List<GovernanceDtos.SubscriptionResponse> subscriptions = request.subscriptions() == null
                ? List.of()
                : request.subscriptions().stream()
                        .map(declaration -> registerOneSdkSubscription(consumer, declaration, request.declarationHash(), now))
                        .toList();
        for (String assetCode : defaultList(request.inputAssets())) {
            repository.findAssetId(assetCode).orElseThrow(() -> new AssetNotFoundException(assetCode));
        }
        for (String assetCode : defaultList(request.outputAssets())) {
            repository.findAssetId(assetCode).orElseThrow(() -> new AssetNotFoundException(assetCode));
        }
        return repository.upsertJob(consumer, request, subscriptions, now);
    }

    public List<GovernanceDtos.SubscriptionResponse> listSubscriptions() {
        return repository.listSubscriptions();
    }

    public GovernanceDtos.SubscriptionResponse getSubscription(String subscriptionId) {
        return repository.findSubscription(subscriptionId)
                .orElseThrow(() -> new SubscriptionNotFoundException(subscriptionId));
    }

    @Transactional
    public GovernanceDtos.SubscriptionResponse updateSubscription(
            String subscriptionId,
            GovernanceDtos.UpdateSubscriptionRequest request
    ) {
        return repository.updateSubscription(subscriptionId, request, Instant.now());
    }

    private GovernanceDtos.SubscriptionResponse registerOneSdkSubscription(
            GovernanceDtos.ConsumerResponse consumer,
            GovernanceDtos.SubscriptionDeclarationRequest declaration,
            String declarationHash,
            Instant now
    ) {
        String assetId = repository.findAssetId(declaration.assetCode())
                .orElseThrow(() -> new AssetNotFoundException(declaration.assetCode()));
        return repository.upsertSubscription(
                assetId,
                declaration.assetCode(),
                consumer,
                declaration,
                SubscriptionSourceType.SDK_STARTUP,
                declarationHash,
                now);
    }

    private List<String> defaultList(List<String> values) {
        return values == null ? List.of() : values;
    }
}
```

- [ ] **Step 7: Implement controllers**

Create `SubscriptionController.java`:

```java
package io.datagov.server.subscription;

import io.datagov.common.dto.GovernanceDtos;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class SubscriptionController {
    private final SubscriptionService subscriptionService;

    public SubscriptionController(SubscriptionService subscriptionService) {
        this.subscriptionService = subscriptionService;
    }

    @PostMapping("/api/assets/{assetCode}/subscriptions")
    public GovernanceDtos.SubscriptionResponse create(
            @PathVariable String assetCode,
            @Valid @RequestBody GovernanceDtos.CreateSubscriptionRequest request
    ) {
        return subscriptionService.createApiSubscription(assetCode, request);
    }

    @GetMapping("/api/subscriptions")
    public List<GovernanceDtos.SubscriptionResponse> list() {
        return subscriptionService.listSubscriptions();
    }

    @GetMapping("/api/subscriptions/{subscriptionId}")
    public GovernanceDtos.SubscriptionResponse get(@PathVariable String subscriptionId) {
        return subscriptionService.getSubscription(subscriptionId);
    }

    @PatchMapping("/api/subscriptions/{subscriptionId}")
    public GovernanceDtos.SubscriptionResponse patch(
            @PathVariable String subscriptionId,
            @RequestBody GovernanceDtos.UpdateSubscriptionRequest request
    ) {
        return subscriptionService.updateSubscription(subscriptionId, request);
    }
}
```

Create `SdkController.java`:

```java
package io.datagov.server.sdk;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.server.subscription.SubscriptionService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/sdk")
public class SdkController {
    private final SubscriptionService subscriptionService;

    public SdkController(SubscriptionService subscriptionService) {
        this.subscriptionService = subscriptionService;
    }

    @PostMapping("/subscriptions/register")
    public GovernanceDtos.SdkSubscriptionRegistrationResponse registerSubscriptions(
            @Valid @RequestBody GovernanceDtos.SdkSubscriptionRegistrationRequest request
    ) {
        return subscriptionService.registerSdkSubscriptions(request);
    }

    @PostMapping("/jobs/register")
    public GovernanceDtos.JobRegistrationResponse registerJob(
            @Valid @RequestBody GovernanceDtos.JobRegistrationRequest request
    ) {
        return subscriptionService.registerJob(request);
    }
}
```

- [ ] **Step 8: Extend exception handler**

Modify `ApiExceptionHandler.java` to include:

```java
@ExceptionHandler(SubscriptionNotFoundException.class)
@ResponseStatus(HttpStatus.NOT_FOUND)
public Map<String, Object> subscriptionNotFound(SubscriptionNotFoundException e) {
    return Map.of("error", "SUBSCRIPTION_NOT_FOUND", "detail", e.getMessage());
}
```

Use this import in `ApiExceptionHandler.java`:

```java
import io.datagov.server.subscription.SubscriptionNotFoundException;
```

- [ ] **Step 9: Run focused server tests**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=SubscriptionControllerTest,SdkRegistrationControllerTest test
```

Expected: `BUILD SUCCESS`.

- [ ] **Step 10: Run all Java tests**

Run:

```bash
cd data-gov-platform
mvn test
```

Expected: `BUILD SUCCESS`.

- [ ] **Step 11: Commit**

```bash
git add data-gov-platform/data-gov-server/src/main/java data-gov-platform/data-gov-server/src/test/java
git commit -m "feat: add subscription and sdk registration APIs"
```

---

### Task 4: Java SDK Core Client

**Files:**
- Modify: `data-gov-platform/data-gov-sdk/pom.xml`
- Create: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DataGovClient.java`
- Create: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DefaultDataGovClient.java`
- Create: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/DataGovClientException.java`
- Create: `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/DefaultDataGovClientTest.java`

- [ ] **Step 1: Add SDK dependencies**

Modify `data-gov-sdk/pom.xml` dependencies to include:

```xml
<dependency>
    <groupId>io.datagov</groupId>
    <artifactId>data-gov-common</artifactId>
    <version>${project.version}</version>
</dependency>
<dependency>
    <groupId>org.springframework</groupId>
    <artifactId>spring-web</artifactId>
</dependency>
<dependency>
    <groupId>com.fasterxml.jackson.core</groupId>
    <artifactId>jackson-databind</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-test</artifactId>
    <scope>test</scope>
</dependency>
```

- [ ] **Step 2: Write failing SDK client tests**

Create `DefaultDataGovClientTest.java`:

```java
package io.datagov.sdk;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.common.enums.ConsumerType;
import io.datagov.common.enums.JobType;
import io.datagov.common.enums.UsageMode;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;
import static org.springframework.http.HttpMethod.POST;

class DefaultDataGovClientTest {
    @Test
    void registersSubscriptions() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://data-gov-server:8080");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        DataGovClient client = new DefaultDataGovClient(builder.build());

        server.expect(requestTo("http://data-gov-server:8080/api/sdk/subscriptions/register"))
                .andExpect(method(POST))
                .andExpect(jsonPath("$.consumer.consumerName").value("rno-dashboard"))
                .andRespond(withSuccess("""
                        {
                          "consumer": {
                            "consumerId": "consumer-1",
                            "consumerType": "MICROSERVICE",
                            "consumerName": "rno-dashboard",
                            "environment": "prod"
                          },
                          "subscriptions": [],
                          "assetCodeToSubscriptionId": {}
                        }
                        """, MediaType.APPLICATION_JSON));

        GovernanceDtos.SdkSubscriptionRegistrationResponse response = client.registerSubscriptions(
                new GovernanceDtos.SdkSubscriptionRegistrationRequest(
                        new GovernanceDtos.ConsumerRequest(
                                "rno-dashboard", ConsumerType.MICROSERVICE, "network-team", "prod", "1.0.0", "pod-1"),
                        "sha256:abc",
                        List.of(new GovernanceDtos.SubscriptionDeclarationRequest(
                                "ads_cell_profile", UsageMode.API_QUERY, "dashboard", List.of("cell_id"), List.of()))));

        assertThat(response.consumer().consumerName()).isEqualTo("rno-dashboard");
        server.verify();
    }

    @Test
    void registersJobDeclaration() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://data-gov-server:8080");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        DataGovClient client = new DefaultDataGovClient(builder.build());

        server.expect(requestTo("http://data-gov-server:8080/api/sdk/jobs/register"))
                .andExpect(method(POST))
                .andExpect(jsonPath("$.jobName").value("cell-hourly-agg"))
                .andRespond(withSuccess("""
                        {
                          "jobId": "job-1",
                          "jobName": "cell-hourly-agg",
                          "jobType": "FLINK",
                          "status": "ACTIVE",
                          "consumer": {
                            "consumerId": "consumer-1",
                            "consumerType": "FLINK_JOB",
                            "consumerName": "cell-hourly-agg",
                            "environment": "prod"
                          },
                          "subscriptions": [],
                          "lastRegisteredAt": "2026-06-10T00:00:00Z"
                        }
                        """, MediaType.APPLICATION_JSON));

        GovernanceDtos.JobRegistrationResponse response = client.registerJob(
                new GovernanceDtos.JobRegistrationRequest(
                        new GovernanceDtos.ConsumerRequest(
                                "cell-hourly-agg", ConsumerType.FLINK_JOB, "network-team", "prod", null, null),
                        "cell-hourly-agg", JobType.FLINK, "network-team", "git://jobs/cell-hourly-agg",
                        null, List.of("ods_ue_signal"), List.of("dwd_session_qos"), "sha256:job",
                        List.of()));

        assertThat(response.jobName()).isEqualTo("cell-hourly-agg");
        server.verify();
    }
}
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-sdk -am -Dtest=DefaultDataGovClientTest test
```

Expected: FAIL because SDK classes do not exist.

- [ ] **Step 4: Implement SDK client interface and exception**

Create `DataGovClient.java`:

```java
package io.datagov.sdk;

import io.datagov.common.dto.GovernanceDtos;

public interface DataGovClient {
    GovernanceDtos.SdkSubscriptionRegistrationResponse registerSubscriptions(
            GovernanceDtos.SdkSubscriptionRegistrationRequest request);

    GovernanceDtos.JobRegistrationResponse registerJob(GovernanceDtos.JobRegistrationRequest request);
}
```

Create `DataGovClientException.java`:

```java
package io.datagov.sdk;

public class DataGovClientException extends RuntimeException {
    public DataGovClientException(String message, Throwable cause) {
        super(message, cause);
    }
}
```

- [ ] **Step 5: Implement RestClient-backed SDK client**

Create `DefaultDataGovClient.java`:

```java
package io.datagov.sdk;

import io.datagov.common.dto.GovernanceDtos;
import org.springframework.web.client.RestClient;

public class DefaultDataGovClient implements DataGovClient {
    private final RestClient restClient;

    public DefaultDataGovClient(RestClient restClient) {
        this.restClient = restClient;
    }

    @Override
    public GovernanceDtos.SdkSubscriptionRegistrationResponse registerSubscriptions(
            GovernanceDtos.SdkSubscriptionRegistrationRequest request
    ) {
        try {
            return restClient.post()
                    .uri("/api/sdk/subscriptions/register")
                    .body(request)
                    .retrieve()
                    .body(GovernanceDtos.SdkSubscriptionRegistrationResponse.class);
        } catch (RuntimeException ex) {
            throw new DataGovClientException("Failed to register data governance subscriptions", ex);
        }
    }

    @Override
    public GovernanceDtos.JobRegistrationResponse registerJob(GovernanceDtos.JobRegistrationRequest request) {
        try {
            return restClient.post()
                    .uri("/api/sdk/jobs/register")
                    .body(request)
                    .retrieve()
                    .body(GovernanceDtos.JobRegistrationResponse.class);
        } catch (RuntimeException ex) {
            throw new DataGovClientException("Failed to register data governance job declaration", ex);
        }
    }
}
```

- [ ] **Step 6: Run focused SDK tests**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-sdk -am -Dtest=DefaultDataGovClientTest test
```

Expected: `BUILD SUCCESS`.

- [ ] **Step 7: Commit**

```bash
git add data-gov-platform/data-gov-sdk/pom.xml data-gov-platform/data-gov-sdk/src/main/java data-gov-platform/data-gov-sdk/src/test/java
git commit -m "feat: add data governance SDK client"
```

---

### Task 5: Spring Boot SDK Startup Auto-Registration

**Files:**
- Modify: `data-gov-platform/data-gov-sdk/pom.xml`
- Create: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovProperties.java`
- Create: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovAutoConfiguration.java`
- Create: `data-gov-platform/data-gov-sdk/src/main/java/io/datagov/sdk/spring/DataGovStartupRegistrar.java`
- Create: `data-gov-platform/data-gov-sdk/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
- Create: `data-gov-platform/data-gov-sdk/src/test/java/io/datagov/sdk/spring/DataGovAutoConfigurationTest.java`

- [ ] **Step 1: Add auto-configuration dependencies**

Add these dependencies to `data-gov-sdk/pom.xml`:

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-autoconfigure</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-configuration-processor</artifactId>
    <optional>true</optional>
</dependency>
```

- [ ] **Step 2: Write failing auto-configuration tests**

Create `DataGovAutoConfigurationTest.java`:

```java
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
                        "data-gov.subscriptions[0].notify-on[0]=SCHEMA_CHANGE")
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
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-sdk -am -Dtest=DataGovAutoConfigurationTest test
```

Expected: FAIL because Spring SDK classes do not exist.

- [ ] **Step 4: Implement configuration properties**

Create `DataGovProperties.java`:

```java
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
    private int registerTimeoutMs = 3000;

    public boolean enabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String endpoint() {
        return endpoint;
    }

    public void setEndpoint(String endpoint) {
        this.endpoint = endpoint;
    }

    public Consumer consumer() {
        return consumer;
    }

    public void setConsumer(Consumer consumer) {
        this.consumer = consumer;
    }

    public List<Subscription> subscriptions() {
        return subscriptions;
    }

    public void setSubscriptions(List<Subscription> subscriptions) {
        this.subscriptions = subscriptions == null ? List.of() : subscriptions;
    }

    public boolean failFast() {
        return failFast;
    }

    public void setFailFast(boolean failFast) {
        this.failFast = failFast;
    }

    public int registerTimeoutMs() {
        return registerTimeoutMs;
    }

    public void setRegisterTimeoutMs(int registerTimeoutMs) {
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

        public void setName(String name) {
            this.name = name;
        }

        public ConsumerType type() {
            return type;
        }

        public void setType(ConsumerType type) {
            this.type = type;
        }

        public String owner() {
            return owner;
        }

        public void setOwner(String owner) {
            this.owner = owner;
        }

        public String environment() {
            return environment;
        }

        public void setEnvironment(String environment) {
            this.environment = environment;
        }

        public String version() {
            return version;
        }

        public void setVersion(String version) {
            this.version = version;
        }

        public String instanceId() {
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

        public void setAssetCode(String assetCode) {
            this.assetCode = assetCode;
        }

        public UsageMode usageMode() {
            return usageMode;
        }

        public void setUsageMode(UsageMode usageMode) {
            this.usageMode = usageMode;
        }

        public String purpose() {
            return purpose;
        }

        public void setPurpose(String purpose) {
            this.purpose = purpose;
        }

        public List<String> fields() {
            return fields;
        }

        public void setFields(List<String> fields) {
            this.fields = fields == null ? List.of() : fields;
        }

        public List<AssetEventType> notifyOn() {
            return notifyOn;
        }

        public void setNotifyOn(List<AssetEventType> notifyOn) {
            this.notifyOn = notifyOn == null ? List.of() : notifyOn;
        }
    }
}
```

- [ ] **Step 5: Implement auto-configuration**

Create `DataGovAutoConfiguration.java`:

```java
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
    public DataGovClient dataGovClient(DataGovProperties properties) {
        return new DefaultDataGovClient(RestClient.builder()
                .baseUrl(properties.endpoint())
                .build());
    }

    @Bean
    @ConditionalOnMissingBean
    public DataGovStartupRegistrar dataGovStartupRegistrar(
            DataGovClient dataGovClient,
            DataGovProperties properties
    ) {
        return new DataGovStartupRegistrar(dataGovClient, properties);
    }
}
```

Create auto-configuration import file:

```text
io.datagov.sdk.spring.DataGovAutoConfiguration
```

- [ ] **Step 6: Implement startup registrar**

Create `DataGovStartupRegistrar.java`:

```java
package io.datagov.sdk.spring;

import io.datagov.common.dto.GovernanceDtos;
import io.datagov.sdk.DataGovClient;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.ApplicationListener;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

public class DataGovStartupRegistrar implements ApplicationListener<ApplicationReadyEvent> {
    private final DataGovClient dataGovClient;
    private final DataGovProperties properties;

    public DataGovStartupRegistrar(DataGovClient dataGovClient, DataGovProperties properties) {
        this.dataGovClient = dataGovClient;
        this.properties = properties;
    }

    @Override
    public void onApplicationEvent(ApplicationReadyEvent event) {
        if (properties.subscriptions().isEmpty()) {
            return;
        }
        try {
            dataGovClient.registerSubscriptions(toRequest());
        } catch (RuntimeException ex) {
            if (properties.failFast()) {
                throw ex;
            }
        }
    }

    GovernanceDtos.SdkSubscriptionRegistrationRequest toRequest() {
        GovernanceDtos.ConsumerRequest consumer = new GovernanceDtos.ConsumerRequest(
                properties.consumer().name(),
                properties.consumer().type(),
                properties.consumer().owner(),
                properties.consumer().environment(),
                properties.consumer().version(),
                properties.consumer().instanceId());

        var declarations = properties.subscriptions().stream()
                .map(subscription -> new GovernanceDtos.SubscriptionDeclarationRequest(
                        subscription.assetCode(),
                        subscription.usageMode(),
                        subscription.purpose(),
                        subscription.fields(),
                        subscription.notifyOn()))
                .toList();

        return new GovernanceDtos.SdkSubscriptionRegistrationRequest(
                consumer,
                declarationHash(consumer.consumerName() + declarations.toString()),
                declarations);
    }

    private String declarationHash(String raw) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(raw.getBytes(StandardCharsets.UTF_8));
            return "sha256:" + HexFormat.of().formatHex(bytes);
        } catch (Exception ex) {
            return "sha256:unavailable";
        }
    }
}
```

- [ ] **Step 7: Run auto-configuration tests**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-sdk -am -Dtest=DataGovAutoConfigurationTest test
```

Expected: `BUILD SUCCESS`.

- [ ] **Step 8: Run all Java tests**

Run:

```bash
cd data-gov-platform
mvn test
```

Expected: `BUILD SUCCESS`.

- [ ] **Step 9: Commit**

```bash
git add data-gov-platform/data-gov-sdk
git commit -m "feat: add SDK startup registration auto config"
```

---

## Plan Self-Review

Spec coverage for this slice:

- Subscription declaration model: Tasks 1, 2, and 3.
- SDK startup registration: Tasks 1, 3, 4, and 5.
- Flink/Spark job declaration registration without run lifecycle: Tasks 1, 2, and 3.
- Removed APIs stay absent: no task adds run start/finish or notification pull/ack endpoints.
- Java SDK only: Tasks 4 and 5.
- GaussDB-oriented persistence: Task 2.

Intentional gaps for later plans:

- Kafka asynchronous notification publishing and SDK listener callbacks.
- `asset_event` and `subscription_notification` tables.
- StarRocks product API and SQL Gateway.
- `query_record` runtime facts.
- `lineage_edge` and impact analysis APIs.
- Drift detection.

No implementation step in this plan modifies Docker Compose. If a later implementation touches infrastructure, follow `AGENTS.md` and check `../shared-data-infra` first.
