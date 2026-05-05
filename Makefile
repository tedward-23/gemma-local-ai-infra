.PHONY: up pull-model down logs ps test config benchmark

up:
	docker compose up --build -d

pull-model:
	docker compose run --rm ollama-model-init

down:
	docker compose down

logs:
	docker compose logs -f api ollama

ps:
	docker compose ps

config:
	docker compose config

test:
	python3 -m compileall src scripts

benchmark:
	python3 scripts/benchmark.py --requests 10 --concurrency 2

