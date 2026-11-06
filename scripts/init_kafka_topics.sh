#!/bin/bash
set -e
echo "Waiting for Kafka..."
cub kafka-ready -b kafka:29092 1 60

kafka-topics --bootstrap-server kafka:29092 --create --if-not-exists \
  --topic "${KAFKA_TOPIC:-fraud-transactions}" --partitions "${KAFKA_PARTITIONS:-6}" --replication-factor 1
kafka-topics --bootstrap-server kafka:29092 --create --if-not-exists \
  --topic "${KAFKA_DLQ_TOPIC:-fraud-transactions-dlq}" --partitions 1 --replication-factor 1

kafka-topics --bootstrap-server kafka:29092 --list
