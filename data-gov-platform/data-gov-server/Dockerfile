# syntax=docker/dockerfile:1.6
FROM maven:3.9.9-eclipse-temurin-17 AS build

WORKDIR /workspace

COPY pom.xml .
COPY data-gov-common/pom.xml data-gov-common/pom.xml
COPY data-gov-server/pom.xml data-gov-server/pom.xml
COPY data-gov-sdk/pom.xml data-gov-sdk/pom.xml

RUN --mount=type=cache,target=/root/.m2 mvn -B -pl data-gov-server -am -DskipTests dependency:go-offline

COPY data-gov-common data-gov-common
COPY data-gov-server data-gov-server
COPY data-gov-sdk data-gov-sdk

RUN --mount=type=cache,target=/root/.m2 mvn -B -pl data-gov-server -am -DskipTests package

FROM eclipse-temurin:17-jre-jammy

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system datagov \
    && useradd --system --gid datagov --home-dir /app --shell /usr/sbin/nologin datagov \
    && mkdir -p /app/data \
    && chown -R datagov:datagov /app

WORKDIR /app

COPY --from=build --chown=datagov:datagov /workspace/data-gov-server/target/data-gov-server-*.jar /app/data-gov-server.jar

USER datagov

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/data-gov-server.jar"]
