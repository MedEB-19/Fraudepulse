.PHONY: setup up up-full down logs train sample test lint reset status drift

COMPOSE      = docker compose
COMPOSE_FULL = docker compose -f docker-compose.yml -f docker-compose.observability.yml -f docker-compose.mlops.yml

setup:        ## create .env from the template
	@test -f .env || cp .env.example .env && echo ".env ready"

sample:       ## generate a small synthetic dataset (smoke test, no Kaggle needed)
	python scripts/make_sample_data.py --rows 50000 --out data/paysim.csv

up:           ## start the core pipeline
	$(COMPOSE) up -d --build

up-full:      ## core + Prometheus/Grafana + MLflow
	$(COMPOSE_FULL) up -d --build

train:        ## distributed XGBoost training inside the Spark cluster
	$(COMPOSE) --profile train run --rm trainer

down:
	$(COMPOSE_FULL) down

logs:
	$(COMPOSE) logs -f --tail=100 spark-stream producer

status:
	$(COMPOSE) ps

drift:        ## PSI drift check (needs Mongo on localhost:27017)
	PYTHONPATH=src python src/monitoring/drift_check.py

test:
	PYTHONPATH=src pytest -q

lint:
	ruff check src tests scripts

reset:
	./scripts/reset.sh
