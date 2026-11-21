# syntax=docker/dockerfile:1
# Apache Tika Server sidecar for DOC, DOCX, ODS and XLSX (D6), reachable only on the internal
# network.

ARG JRE_IMAGE=eclipse-temurin:25.0.5.1_2-jre-alpine-3.24

# --- download: pinned JAR, verified against the checksum from archive.apache.org -----------------
FROM ${JRE_IMAGE} AS download
ARG TIKA_VERSION=3.3.2
# Official checksum from tika-server-standard-3.3.2.jar.sha512 (Apache publishes only SHA-512).
ARG TIKA_SHA512=fb1f2fe57ac458b09d44d41d816f582e1d2fc93488acff6275caf414d8d5ef94e42166edc0b488dc2fb6ef3aa21fab62b107c43b9060385ff6d675e393c2c9e9
RUN wget -q -O /tmp/tika-server.jar \
      "https://archive.apache.org/dist/tika/${TIKA_VERSION}/tika-server-standard-${TIKA_VERSION}.jar" \
 && echo "${TIKA_SHA512}  /tmp/tika-server.jar" | sha512sum -c - \
 && mkdir -p /opt/tika \
 && mv /tmp/tika-server.jar /opt/tika/tika-server.jar

# --- runtime -------------------------------------------------------------------------------------
FROM ${JRE_IMAGE}

RUN addgroup -S -g 10001 tika \
 && adduser -S -D -H -u 10001 -G tika -h /nonexistent -s /sbin/nologin tika

COPY --from=download /opt/tika/tika-server.jar /opt/tika/tika-server.jar

# Heap relative to the container memory limit. The options also reach the forked child that Tika
# Server parses in; on OOM the child exits and the watchdog restarts it.
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=50 -XX:+ExitOnOutOfMemoryError -Djava.io.tmpdir=/tmp"

USER tika:tika
EXPOSE 9998

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:9998/version || exit 1

ENTRYPOINT ["java", "-jar", "/opt/tika/tika-server.jar", "--host", "0.0.0.0", "--port", "9998"]
