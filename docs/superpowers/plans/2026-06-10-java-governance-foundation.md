# Java Governance Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first independently testable slice of the data product governance platform: a Java/Spring Boot multi-module service with GaussDB-oriented schema migrations and basic asset registration/query APIs.

**Architecture:** Add a new `data-gov-platform` Maven multi-module project alongside the existing Python/FastAPI code. The first slice contains shared DTO/enums, a Spring Boot server, Flyway migrations for core asset metadata tables, and basic REST APIs backed by JDBC/MyBatis-style repositories. It does not remove the existing Python backend yet.

**Tech Stack:** Java 17, Spring Boot 3.3.x, Maven, Flyway, JDBC/Hikari, H2 for tests, GaussDB-compatible SQL style, JUnit 5, Spring MockMvc.

---

## Scope Notes

The approved spec covers multiple subsystems: asset catalog, subscriptions, SDK, StarRocks query gateway, lineage, events, notifications, and drift. This plan intentionally implements only the first foundation slice:

- Java multi-module project skeleton.
- Core shared enums and DTOs.
- GaussDB-oriented DDL for `data_asset`, `asset_field`, and `asset_physical_binding`.
- Spring Boot server bootstrapping.
- Basic asset register/list/get/schema/binding APIs.

Later plans should add subscription/SDK, query gateway, lineage, events, and governance drift.

## File Structure

Create:

- `data-gov-platform/pom.xml`  
  Parent Maven project. Defines Java 17, Spring Boot dependency management, module list, compiler and surefire settings.

- `data-gov-platform/data-gov-common/pom.xml`  
  Shared DTO/enums module used by server and future SDK.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/AssetType.java`  
  Asset type enum.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/AssetEngine.java`  
  Engine enum.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LifecycleStatus.java`  
  Lifecycle enum.

- `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/AssetDtos.java`  
  First-slice DTO records for asset registration and responses.

- `data-gov-platform/data-gov-server/pom.xml`  
  Spring Boot service module.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/DataGovServerApplication.java`  
  Spring Boot entrypoint.

- `data-gov-platform/data-gov-server/src/main/resources/application.yml`  
  Default app config for server, datasource, Flyway and management endpoints.

- `data-gov-platform/data-gov-server/src/main/resources/db/migration/V1__core_asset_catalog.sql`  
  Flyway migration for asset catalog tables.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetRepository.java`  
  JDBC repository for assets, fields and physical bindings.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetService.java`  
  Business service for register/list/get/schema/binding.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetController.java`  
  REST API controller.

- `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`  
  Small exception-to-response mapper.

- `data-gov-platform/data-gov-server/src/test/resources/application-test.yml`  
  H2/Flyway config for tests.

- `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/asset/AssetControllerTest.java`  
  MockMvc integration tests.

- `data-gov-platform/data-gov-sdk/pom.xml`  
  Placeholder SDK module that compiles but contains no runtime SDK behavior in this slice.

Modify:

- None outside `data-gov-platform/` for this slice.

---

### Task 1: Maven Multi-Module Skeleton

**Files:**
- Create: `data-gov-platform/pom.xml`
- Create: `data-gov-platform/data-gov-common/pom.xml`
- Create: `data-gov-platform/data-gov-server/pom.xml`
- Create: `data-gov-platform/data-gov-sdk/pom.xml`

- [ ] **Step 1: Write the parent Maven project**

Create `data-gov-platform/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>io.datagov</groupId>
    <artifactId>data-gov-platform</artifactId>
    <version>0.1.0-SNAPSHOT</version>
    <packaging>pom</packaging>

    <modules>
        <module>data-gov-common</module>
        <module>data-gov-server</module>
        <module>data-gov-sdk</module>
    </modules>

    <properties>
        <java.version>17</java.version>
        <spring.boot.version>3.3.5</spring.boot.version>
        <maven.compiler.release>${java.version}</maven.compiler.release>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <project.reporting.outputEncoding>UTF-8</project.reporting.outputEncoding>
    </properties>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-dependencies</artifactId>
                <version>${spring.boot.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>

    <build>
        <pluginManagement>
            <plugins>
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-compiler-plugin</artifactId>
                    <version>3.13.0</version>
                    <configuration>
                        <release>${java.version}</release>
                    </configuration>
                </plugin>
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-surefire-plugin</artifactId>
                    <version>3.5.2</version>
                </plugin>
            </plugins>
        </pluginManagement>
    </build>
</project>
```

- [ ] **Step 2: Write common module POM**

Create `data-gov-platform/data-gov-common/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>io.datagov</groupId>
        <artifactId>data-gov-platform</artifactId>
        <version>0.1.0-SNAPSHOT</version>
    </parent>

    <artifactId>data-gov-common</artifactId>

    <dependencies>
        <dependency>
            <groupId>jakarta.validation</groupId>
            <artifactId>jakarta.validation-api</artifactId>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 3: Write server module POM**

Create `data-gov-platform/data-gov-server/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>io.datagov</groupId>
        <artifactId>data-gov-platform</artifactId>
        <version>0.1.0-SNAPSHOT</version>
    </parent>

    <artifactId>data-gov-server</artifactId>

    <dependencies>
        <dependency>
            <groupId>io.datagov</groupId>
            <artifactId>data-gov-common</artifactId>
            <version>${project.version}</version>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-jdbc</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.flywaydb</groupId>
            <artifactId>flyway-core</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <version>${spring.boot.version}</version>
            </plugin>
        </plugins>
    </build>
</project>
```

- [ ] **Step 4: Write SDK placeholder module POM**

Create `data-gov-platform/data-gov-sdk/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>io.datagov</groupId>
        <artifactId>data-gov-platform</artifactId>
        <version>0.1.0-SNAPSHOT</version>
    </parent>

    <artifactId>data-gov-sdk</artifactId>

    <dependencies>
        <dependency>
            <groupId>io.datagov</groupId>
            <artifactId>data-gov-common</artifactId>
            <version>${project.version}</version>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 5: Verify Maven skeleton compiles**

Run:

```bash
cd data-gov-platform
mvn test
```

Expected: `BUILD SUCCESS`. There are no tests yet.

- [ ] **Step 6: Commit**

```bash
git add data-gov-platform/pom.xml data-gov-platform/data-gov-common/pom.xml data-gov-platform/data-gov-server/pom.xml data-gov-platform/data-gov-sdk/pom.xml
git commit -m "feat: add Java governance Maven skeleton"
```

---

### Task 2: Shared Asset DTOs and Enums

**Files:**
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/AssetType.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/AssetEngine.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/enums/LifecycleStatus.java`
- Create: `data-gov-platform/data-gov-common/src/main/java/io/datagov/common/dto/AssetDtos.java`

- [ ] **Step 1: Add enums**

Create `AssetType.java`:

```java
package io.datagov.common.enums;

public enum AssetType {
    TABLE,
    STREAM,
    VIEW,
    API,
    JOB_OUTPUT
}
```

Create `AssetEngine.java`:

```java
package io.datagov.common.enums;

public enum AssetEngine {
    STARROCKS,
    HIVE,
    ICEBERG,
    GAUSSDB,
    KAFKA
}
```

Create `LifecycleStatus.java`:

```java
package io.datagov.common.enums;

public enum LifecycleStatus {
    DRAFT,
    ACTIVE,
    DEPRECATED,
    OFFLINE
}
```

- [ ] **Step 2: Add DTO records**

Create `AssetDtos.java`:

```java
package io.datagov.common.dto;

import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LifecycleStatus;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class AssetDtos {
    private AssetDtos() {
    }

    public record RegisterAssetRequest(
            @NotBlank String assetCode,
            String assetName,
            @NotNull AssetType assetType,
            @NotNull AssetEngine engine,
            String domain,
            String owner,
            String description,
            LifecycleStatus lifecycleStatus,
            Boolean queryable,
            Boolean federatedQueryable,
            @Valid List<FieldRequest> fields,
            @Valid PhysicalBindingRequest physicalBinding
    ) {
    }

    public record FieldRequest(
            @NotBlank String fieldName,
            @NotBlank String fieldType,
            Integer ordinalPosition,
            Boolean nullable,
            Boolean partitionKey,
            Boolean primaryKey,
            Boolean eventTime,
            String description,
            String expression
    ) {
    }

    public record PhysicalBindingRequest(
            @NotNull AssetEngine engine,
            String catalogName,
            String databaseName,
            String schemaName,
            String tableName,
            String topicName,
            String format,
            String locationUri,
            String connectionRef,
            String queryAdapter,
            Map<String, Object> properties
    ) {
    }

    public record AssetResponse(
            String assetId,
            String assetCode,
            String assetName,
            AssetType assetType,
            AssetEngine engine,
            String domain,
            String owner,
            String description,
            LifecycleStatus lifecycleStatus,
            int schemaVersion,
            boolean queryable,
            boolean federatedQueryable,
            Instant createdAt,
            Instant updatedAt
    ) {
    }

    public record FieldResponse(
            String fieldId,
            String assetId,
            String fieldName,
            String fieldType,
            Integer ordinalPosition,
            boolean nullable,
            boolean partitionKey,
            boolean primaryKey,
            boolean eventTime,
            String description,
            String expression,
            int version
    ) {
    }

    public record PhysicalBindingResponse(
            String bindingId,
            String assetId,
            AssetEngine engine,
            String catalogName,
            String databaseName,
            String schemaName,
            String tableName,
            String topicName,
            String format,
            String locationUri,
            String connectionRef,
            String queryAdapter,
            Map<String, Object> properties,
            boolean active
    ) {
    }

    public record AssetDetailResponse(
            AssetResponse asset,
            List<FieldResponse> fields,
            PhysicalBindingResponse binding
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
git add data-gov-platform/data-gov-common/src/main/java
git commit -m "feat: add shared asset DTOs"
```

---

### Task 3: Server Bootstrap and Flyway Core Asset Schema

**Files:**
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/DataGovServerApplication.java`
- Create: `data-gov-platform/data-gov-server/src/main/resources/application.yml`
- Create: `data-gov-platform/data-gov-server/src/main/resources/db/migration/V1__core_asset_catalog.sql`
- Create: `data-gov-platform/data-gov-server/src/test/resources/application-test.yml`

- [ ] **Step 1: Add Spring Boot application**

Create `DataGovServerApplication.java`:

```java
package io.datagov.server;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class DataGovServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(DataGovServerApplication.class, args);
    }
}
```

- [ ] **Step 2: Add application config**

Create `application.yml`:

```yaml
server:
  port: 8080

spring:
  application:
    name: data-gov-server
  datasource:
    url: ${DATAGOV_GAUSSDB_JDBC_URL:jdbc:postgresql://localhost:5432/data_gov}
    username: ${DATAGOV_GAUSSDB_USER:data_gov}
    password: ${DATAGOV_GAUSSDB_PASSWORD:data_gov}
    driver-class-name: org.postgresql.Driver
  flyway:
    enabled: true
    locations: classpath:db/migration

management:
  endpoints:
    web:
      exposure:
        include: health,info
```

Create `application-test.yml`:

```yaml
spring:
  datasource:
    url: jdbc:h2:mem:data_gov;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH
    username: sa
    password:
    driver-class-name: org.h2.Driver
  flyway:
    enabled: true
    locations: classpath:db/migration
```

- [ ] **Step 3: Add Flyway migration**

Create `V1__core_asset_catalog.sql`:

```sql
create table data_asset (
    asset_id varchar(64) primary key,
    asset_code varchar(128) not null unique,
    asset_name varchar(256),
    asset_type varchar(32) not null,
    engine varchar(32) not null,
    domain varchar(128),
    owner varchar(128),
    description text,
    lifecycle_status varchar(32) not null,
    schema_version integer not null default 1,
    queryable boolean not null default false,
    federated_queryable boolean not null default false,
    created_at timestamp not null,
    updated_at timestamp not null
);

create index idx_data_asset_type_engine on data_asset(asset_type, engine);
create index idx_data_asset_domain on data_asset(domain);
create index idx_data_asset_lifecycle_status on data_asset(lifecycle_status);

create table asset_field (
    field_id varchar(64) primary key,
    asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    field_name varchar(128) not null,
    field_type varchar(128) not null,
    ordinal_position integer,
    nullable boolean not null default true,
    partition_key boolean not null default false,
    primary_key boolean not null default false,
    event_time boolean not null default false,
    description text,
    expression text,
    version integer not null default 1,
    created_at timestamp not null,
    updated_at timestamp not null,
    constraint uk_asset_field_name unique(asset_id, field_name)
);

create index idx_asset_field_asset_id on asset_field(asset_id);
create index idx_asset_field_name on asset_field(field_name);

create table asset_physical_binding (
    binding_id varchar(64) primary key,
    asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    engine varchar(32) not null,
    catalog_name varchar(128),
    database_name varchar(128),
    schema_name varchar(128),
    table_name varchar(128),
    topic_name varchar(128),
    format varchar(64),
    location_uri text,
    connection_ref varchar(256),
    query_adapter varchar(64),
    properties text,
    active boolean not null default true,
    created_at timestamp not null,
    updated_at timestamp not null
);

create index idx_asset_binding_asset_id on asset_physical_binding(asset_id);
create index idx_asset_binding_table on asset_physical_binding(catalog_name, database_name, table_name);
create index idx_asset_binding_topic on asset_physical_binding(topic_name);
```

Use `properties text` for this first slice so H2 and GaussDB/PostgreSQL tests stay simple. A later migration can move to `jsonb` if needed.

- [ ] **Step 4: Verify server module boots in tests**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-server -am test
```

Expected: `BUILD SUCCESS`.

- [ ] **Step 5: Commit**

```bash
git add data-gov-platform/data-gov-server/src/main/java/io/datagov/server/DataGovServerApplication.java data-gov-platform/data-gov-server/src/main/resources data-gov-platform/data-gov-server/src/test/resources
git commit -m "feat: add governance server bootstrap and schema"
```

---

### Task 4: Asset Repository, Service, Controller and Tests

**Files:**
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetRepository.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetService.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/asset/AssetController.java`
- Create: `data-gov-platform/data-gov-server/src/main/java/io/datagov/server/common/ApiExceptionHandler.java`
- Create: `data-gov-platform/data-gov-server/src/test/java/io/datagov/server/asset/AssetControllerTest.java`

- [ ] **Step 1: Write failing controller integration test**

Create `AssetControllerTest.java`:

```java
package io.datagov.server.asset;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AssetControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Test
    void registerAndReadTableAsset() throws Exception {
        String payload = """
                {
                  "assetCode": "ads_cell_profile",
                  "assetName": "小区画像指标宽表",
                  "assetType": "TABLE",
                  "engine": "STARROCKS",
                  "domain": "rno",
                  "owner": "network-team",
                  "description": "小区画像指标宽表",
                  "queryable": true,
                  "federatedQueryable": true,
                  "physicalBinding": {
                    "engine": "STARROCKS",
                    "catalogName": "default_catalog",
                    "databaseName": "data_gov",
                    "tableName": "ads_cell_profile",
                    "queryAdapter": "STARROCKS"
                  },
                  "fields": [
                    {"fieldName": "cell_id", "fieldType": "VARCHAR", "ordinalPosition": 1, "nullable": false},
                    {"fieldName": "coverage_score", "fieldType": "DOUBLE", "ordinalPosition": 2, "nullable": true}
                  ]
                }
                """;

        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.assetCode").value("ads_cell_profile"))
                .andExpect(jsonPath("$.asset.queryable").value(true))
                .andExpect(jsonPath("$.fields", hasSize(2)))
                .andExpect(jsonPath("$.binding.catalogName").value("default_catalog"));

        mockMvc.perform(get("/api/assets"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].assetCode").value("ads_cell_profile"));

        mockMvc.perform(get("/api/assets/ads_cell_profile/schema"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(2)))
                .andExpect(jsonPath("$[0].fieldName").value("cell_id"));

        mockMvc.perform(get("/api/assets/ads_cell_profile/binding"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tableName").value("ads_cell_profile"));
    }

    @Test
    void kafkaAssetCanRegisterButIsNotQueryable() throws Exception {
        String payload = """
                {
                  "assetCode": "ods_ue_signal",
                  "assetType": "STREAM",
                  "engine": "KAFKA",
                  "queryable": true,
                  "federatedQueryable": true,
                  "physicalBinding": {
                    "engine": "KAFKA",
                    "topicName": "ods_ue_signal",
                    "format": "JSON"
                  },
                  "fields": [
                    {"fieldName": "imsi", "fieldType": "STRING"},
                    {"fieldName": "rsrp", "fieldType": "DOUBLE"}
                  ]
                }
                """;

        mockMvc.perform(post("/api/assets/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.asset.assetType").value("STREAM"))
                .andExpect(jsonPath("$.asset.engine").value("KAFKA"))
                .andExpect(jsonPath("$.asset.queryable").value(false))
                .andExpect(jsonPath("$.asset.federatedQueryable").value(false));
    }

    @Test
    void unknownAssetReturns404() throws Exception {
        mockMvc.perform(get("/api/assets/missing_asset"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("ASSET_NOT_FOUND"));
    }
}
```

- [ ] **Step 2: Run test to verify it fails before implementation**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=AssetControllerTest test
```

Expected: FAIL because `AssetController` does not exist.

- [ ] **Step 3: Implement repository**

Create `AssetRepository.java` with focused JDBC methods:

```java
package io.datagov.server.asset;

import io.datagov.common.dto.AssetDtos.AssetResponse;
import io.datagov.common.dto.AssetDtos.FieldResponse;
import io.datagov.common.dto.AssetDtos.PhysicalBindingResponse;
import io.datagov.common.dto.AssetDtos.RegisterAssetRequest;
import io.datagov.common.enums.AssetEngine;
import io.datagov.common.enums.AssetType;
import io.datagov.common.enums.LifecycleStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public class AssetRepository {
    private final JdbcTemplate jdbc;

    public AssetRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional
    public String upsertAsset(String assetId, RegisterAssetRequest req, boolean queryable, boolean federatedQueryable) {
        Instant now = Instant.now();
        String existing = jdbc.query(
                "select asset_id from data_asset where asset_code = ?",
                rs -> rs.next() ? rs.getString("asset_id") : null,
                req.assetCode()
        );
        LifecycleStatus lifecycle = req.lifecycleStatus() == null ? LifecycleStatus.ACTIVE : req.lifecycleStatus();
        String name = req.assetName() == null ? req.assetCode() : req.assetName();
        if (existing == null) {
            jdbc.update("""
                            insert into data_asset(asset_id, asset_code, asset_name, asset_type, engine, domain, owner,
                              description, lifecycle_status, schema_version, queryable, federated_queryable, created_at, updated_at)
                            values (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                            """,
                    assetId, req.assetCode(), name, req.assetType().name(), req.engine().name(), req.domain(), req.owner(),
                    req.description(), lifecycle.name(), queryable, federatedQueryable, now, now);
            return assetId;
        }
        jdbc.update("""
                        update data_asset
                        set asset_name = ?, asset_type = ?, engine = ?, domain = ?, owner = ?, description = ?,
                            lifecycle_status = ?, queryable = ?, federated_queryable = ?, updated_at = ?
                        where asset_id = ?
                        """,
                name, req.assetType().name(), req.engine().name(), req.domain(), req.owner(), req.description(),
                lifecycle.name(), queryable, federatedQueryable, now, existing);
        return existing;
    }

    @Transactional
    public void replaceFields(String assetId, RegisterAssetRequest req) {
        jdbc.update("delete from asset_field where asset_id = ?", assetId);
        if (req.fields() == null) {
            return;
        }
        Instant now = Instant.now();
        int index = 1;
        for (var field : req.fields()) {
            Integer ordinal = field.ordinalPosition() == null ? index : field.ordinalPosition();
            jdbc.update("""
                            insert into asset_field(field_id, asset_id, field_name, field_type, ordinal_position,
                              nullable, partition_key, primary_key, event_time, description, expression, version, created_at, updated_at)
                            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                            """,
                    "field_" + assetId + "_" + field.fieldName(), assetId, field.fieldName(), field.fieldType(), ordinal,
                    field.nullable() == null || field.nullable(),
                    Boolean.TRUE.equals(field.partitionKey()),
                    Boolean.TRUE.equals(field.primaryKey()),
                    Boolean.TRUE.equals(field.eventTime()),
                    field.description(), field.expression(), now, now);
            index++;
        }
    }

    @Transactional
    public void replaceBinding(String assetId, RegisterAssetRequest req) {
        jdbc.update("update asset_physical_binding set active = false where asset_id = ?", assetId);
        if (req.physicalBinding() == null) {
            return;
        }
        Instant now = Instant.now();
        var binding = req.physicalBinding();
        jdbc.update("""
                        insert into asset_physical_binding(binding_id, asset_id, engine, catalog_name, database_name,
                          schema_name, table_name, topic_name, format, location_uri, connection_ref, query_adapter,
                          properties, active, created_at, updated_at)
                        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, true, ?, ?)
                        """,
                "bind_" + assetId, assetId, binding.engine().name(), binding.catalogName(), binding.databaseName(),
                binding.schemaName(), binding.tableName(), binding.topicName(), binding.format(), binding.locationUri(),
                binding.connectionRef(), binding.queryAdapter(), binding.properties() == null ? null : binding.properties().toString(),
                now, now);
    }

    public List<AssetResponse> listAssets() {
        return jdbc.query("select * from data_asset order by asset_code", assetMapper());
    }

    public Optional<AssetResponse> findAsset(String assetCode) {
        List<AssetResponse> rows = jdbc.query("select * from data_asset where asset_code = ?", assetMapper(), assetCode);
        return rows.stream().findFirst();
    }

    public List<FieldResponse> fields(String assetId) {
        return jdbc.query("select * from asset_field where asset_id = ? order by ordinal_position, field_name", fieldMapper(), assetId);
    }

    public Optional<PhysicalBindingResponse> activeBinding(String assetId) {
        List<PhysicalBindingResponse> rows = jdbc.query(
                "select * from asset_physical_binding where asset_id = ? and active = true order by created_at desc",
                bindingMapper(), assetId);
        return rows.stream().findFirst();
    }

    private RowMapper<AssetResponse> assetMapper() {
        return (rs, rowNum) -> new AssetResponse(
                rs.getString("asset_id"),
                rs.getString("asset_code"),
                rs.getString("asset_name"),
                AssetType.valueOf(rs.getString("asset_type")),
                AssetEngine.valueOf(rs.getString("engine")),
                rs.getString("domain"),
                rs.getString("owner"),
                rs.getString("description"),
                LifecycleStatus.valueOf(rs.getString("lifecycle_status")),
                rs.getInt("schema_version"),
                rs.getBoolean("queryable"),
                rs.getBoolean("federated_queryable"),
                rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at").toInstant()
        );
    }

    private RowMapper<FieldResponse> fieldMapper() {
        return (rs, rowNum) -> new FieldResponse(
                rs.getString("field_id"),
                rs.getString("asset_id"),
                rs.getString("field_name"),
                rs.getString("field_type"),
                (Integer) rs.getObject("ordinal_position"),
                rs.getBoolean("nullable"),
                rs.getBoolean("partition_key"),
                rs.getBoolean("primary_key"),
                rs.getBoolean("event_time"),
                rs.getString("description"),
                rs.getString("expression"),
                rs.getInt("version")
        );
    }

    private RowMapper<PhysicalBindingResponse> bindingMapper() {
        return (ResultSet rs, int rowNum) -> new PhysicalBindingResponse(
                rs.getString("binding_id"),
                rs.getString("asset_id"),
                AssetEngine.valueOf(rs.getString("engine")),
                rs.getString("catalog_name"),
                rs.getString("database_name"),
                rs.getString("schema_name"),
                rs.getString("table_name"),
                rs.getString("topic_name"),
                rs.getString("format"),
                rs.getString("location_uri"),
                rs.getString("connection_ref"),
                rs.getString("query_adapter"),
                Map.of(),
                rs.getBoolean("active")
        );
    }
}
```

- [ ] **Step 4: Implement service**

Create `AssetService.java`:

```java
package io.datagov.server.asset;

import io.datagov.common.dto.AssetDtos.AssetDetailResponse;
import io.datagov.common.dto.AssetDtos.AssetResponse;
import io.datagov.common.dto.AssetDtos.FieldResponse;
import io.datagov.common.dto.AssetDtos.PhysicalBindingResponse;
import io.datagov.common.dto.AssetDtos.RegisterAssetRequest;
import io.datagov.common.enums.AssetEngine;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
public class AssetService {
    private final AssetRepository repository;

    public AssetService(AssetRepository repository) {
        this.repository = repository;
    }

    @Transactional
    public AssetDetailResponse register(RegisterAssetRequest req) {
        boolean queryable = Boolean.TRUE.equals(req.queryable());
        boolean federatedQueryable = Boolean.TRUE.equals(req.federatedQueryable());
        if (req.engine() == AssetEngine.KAFKA) {
            queryable = false;
            federatedQueryable = false;
        }
        String assetId = repository.upsertAsset("asset_" + UUID.randomUUID(), req, queryable, federatedQueryable);
        repository.replaceFields(assetId, req);
        repository.replaceBinding(assetId, req);
        return detail(req.assetCode());
    }

    public List<AssetResponse> list() {
        return repository.listAssets();
    }

    public AssetDetailResponse detail(String assetCode) {
        AssetResponse asset = repository.findAsset(assetCode).orElseThrow(() -> new AssetNotFoundException(assetCode));
        return new AssetDetailResponse(asset, repository.fields(asset.assetId()), repository.activeBinding(asset.assetId()).orElse(null));
    }

    public List<FieldResponse> schema(String assetCode) {
        return detail(assetCode).fields();
    }

    public PhysicalBindingResponse binding(String assetCode) {
        PhysicalBindingResponse binding = detail(assetCode).binding();
        if (binding == null) {
            throw new AssetNotFoundException(assetCode + " binding");
        }
        return binding;
    }

    public static class AssetNotFoundException extends RuntimeException {
        public AssetNotFoundException(String assetCode) {
            super(assetCode);
        }
    }
}
```

- [ ] **Step 5: Implement controller**

Create `AssetController.java`:

```java
package io.datagov.server.asset;

import io.datagov.common.dto.AssetDtos.AssetDetailResponse;
import io.datagov.common.dto.AssetDtos.AssetResponse;
import io.datagov.common.dto.AssetDtos.FieldResponse;
import io.datagov.common.dto.AssetDtos.PhysicalBindingResponse;
import io.datagov.common.dto.AssetDtos.RegisterAssetRequest;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/assets")
public class AssetController {
    private final AssetService service;

    public AssetController(AssetService service) {
        this.service = service;
    }

    @PostMapping("/register")
    public AssetDetailResponse register(@Valid @RequestBody RegisterAssetRequest request) {
        return service.register(request);
    }

    @GetMapping
    public List<AssetResponse> list() {
        return service.list();
    }

    @GetMapping("/{assetCode}")
    public AssetDetailResponse detail(@PathVariable String assetCode) {
        return service.detail(assetCode);
    }

    @GetMapping("/{assetCode}/schema")
    public List<FieldResponse> schema(@PathVariable String assetCode) {
        return service.schema(assetCode);
    }

    @GetMapping("/{assetCode}/binding")
    public PhysicalBindingResponse binding(@PathVariable String assetCode) {
        return service.binding(assetCode);
    }
}
```

- [ ] **Step 6: Implement exception handler**

Create `ApiExceptionHandler.java`:

```java
package io.datagov.server.common;

import io.datagov.server.asset.AssetService.AssetNotFoundException;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(AssetNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public Map<String, Object> assetNotFound(AssetNotFoundException e) {
        return Map.of("error", "ASSET_NOT_FOUND", "detail", e.getMessage());
    }
}
```

- [ ] **Step 7: Run test to verify it passes**

Run:

```bash
cd data-gov-platform
mvn -pl data-gov-server -am -Dtest=AssetControllerTest test
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
git add data-gov-platform/data-gov-server/src/main/java data-gov-platform/data-gov-server/src/test/java
git commit -m "feat: add asset catalog API"
```

---

## Plan Self-Review

Spec coverage for this first slice:

- Java Spring Boot service skeleton: Task 1 and Task 3.
- Shared DTO/enums: Task 2.
- GaussDB-oriented core asset metadata schema: Task 3.
- Basic asset registration, discovery, schema and binding APIs: Task 4.
- Kafka as STREAM but not queryable: Task 4 test and service rule.

Intentional gaps for later plans:

- Subscription and SDK startup registration.
- Flink/Spark job reporter.
- StarRocks product query and SQL Gateway.
- Lineage edge APIs.
- Asset events, notifications and usage drift.

No implementation step in this plan modifies Docker Compose. If later implementation touches infrastructure, follow `AGENTS.md` and check `../shared-data-infra` first.
