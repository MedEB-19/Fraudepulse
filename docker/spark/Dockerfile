# One image for Spark master, workers, training and streaming (same Python/Java everywhere).
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless libgomp1 procps curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s "$(dirname "$(dirname "$(readlink -f "$(which java)")")")" /opt/java

ENV JAVA_HOME=/opt/java \
    SPARK_HOME=/usr/local/lib/python3.11/site-packages/pyspark \
    PYSPARK_PYTHON=python3 \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1
ENV PATH="${SPARK_HOME}/bin:${PATH}"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Arrow (used by XGBoost's pandas UDFs) needs this JVM flag on Java 17+
RUN printf 'spark.driver.extraJavaOptions   -Dio.netty.tryReflectionSetAccessible=true\nspark.executor.extraJavaOptions -Dio.netty.tryReflectionSetAccessible=true\n' \
    > ${SPARK_HOME}/conf/spark-defaults.conf

COPY src/fraudpulse /app/src/fraudpulse
COPY src/jobs /app/src/jobs
COPY src/monitoring /app/src/monitoring
RUN mkdir -p /app/models /app/data /app/checkpoints
