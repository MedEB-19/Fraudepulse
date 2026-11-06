#!/bin/bash
# Wipe containers + volumes (Kafka data, Mongo data, Spark checkpoints). Keeps models/ and data/.
docker compose -f docker-compose.yml -f docker-compose.observability.yml -f docker-compose.mlops.yml down -v --remove-orphans
echo "Reset done. Start again with: make up"
