# syntax=docker/dockerfile:1.6
FROM python:3.11-slim-bookworm AS base

ARG SPARK_VERSION=3.5.4
ARG FLINK_VERSION=1.19.1
ARG HADOOP_VERSION=3.3.6
ARG MAVEN_VERSION=3.9.6

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    SPARK_HOME=/opt/spark \
    FLINK_HOME=/opt/flink \
    HADOOP_HOME=/opt/hadoop \
    HADOOP_CONF_DIR=/etc/hadoop \
    PATH=/opt/spark/bin:/opt/flink/bin:/opt/hadoop/bin:/opt/maven/bin:/usr/lib/jvm/java-17-openjdk-amd64/bin:$PATH

# 1) JDK + base utils
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk-headless curl ca-certificates git tini procps tar gzip \
    && rm -rf /var/lib/apt/lists/*

# 2) Maven
RUN curl -fsSL "https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz" \
    | tar -xz -C /opt && ln -s /opt/apache-maven-${MAVEN_VERSION} /opt/maven

# 3) Spark client
RUN curl -fsSL "https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop3.tgz" \
    | tar -xz -C /opt && mv /opt/spark-${SPARK_VERSION}-bin-hadoop3 /opt/spark

# 4) Flink client
RUN curl -fsSL "https://archive.apache.org/dist/flink/flink-${FLINK_VERSION}/flink-${FLINK_VERSION}-bin-scala_2.12.tgz" \
    | tar -xz -C /opt && mv /opt/flink-${FLINK_VERSION} /opt/flink

# 5) Hadoop client (含 hdfs / yarn CLI)
RUN curl -fsSL "https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz" \
    | tar -xz -C /opt && mv /opt/hadoop-${HADOOP_VERSION} /opt/hadoop

WORKDIR /app

COPY pyproject.toml /app/
COPY backend/ /app/backend/

RUN pip install --no-cache-dir -e ".[runtime]"

# Pre-warm bge model (slice 2a 已加)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

ENV PYTHONPATH=/app
EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
