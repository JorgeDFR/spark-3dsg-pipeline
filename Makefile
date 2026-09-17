SHELL := /bin/bash
.DEFAULT_GOAL := help

PROFILE ?= core
DATASET ?= spot
COMPOSE := docker compose
CONTAINER_HOME := /home/spark
PIPELINE_ROOT := $(CONTAINER_HOME)/spark-3dsg-pipeline
INSPECT_ARGS ?=
PREPARE_ARGS ?=
RUN_ARGS ?=
HYDRA_CONFIG ?=
LABELS_CONFIG ?=
DSG ?=
VISUALIZATION_PROFILE ?=

ifeq ($(PROFILE),core)
SERVICE := core
else ifeq ($(PROFILE),gpu)
SERVICE := pipeline
else
$(error PROFILE must be core or gpu)
endif

.PHONY: help build models prepare-data shell dev-shell validate-bag run inspect rviz gpu-smoke test lint clean config lock-dependencies

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target> [PROFILE=core|gpu] [VAR=value]\n\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

config: ## Validate the resolved Compose configuration
	@$(COMPOSE) config --quiet

build: ## Build the exact-SHA v1 snapshot with PROFILE=core|gpu
ifeq ($(PROFILE),core)
	@$(COMPOSE) --profile core build core
else ifeq ($(PROFILE),gpu)
	@$(COMPOSE) --profile gpu build pipeline
endif

models: ## Download/checksum closed-set and YOLOE weights into the model mount
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) $(PIPELINE_ROOT)/scripts/download_models.sh $(PROFILE)

prepare-data: ## Detect/extract/convert known Spot and uHumans2 example bags
	@$(COMPOSE) --profile tools run --rm --build data-setup \
		$(PIPELINE_ROOT)/scripts/prepare_example_bags.py $(PREPARE_ARGS)

shell: ## Open an interactive shell in the selected image
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) bash

dev-shell: ## Open the compiler/source development image
	@$(COMPOSE) --profile dev run --rm --build core-dev bash

validate-bag: ## Validate BAG against DATASET before mapping
	@test -n "$(BAG)" || { echo "BAG is required (container path, normally $(CONTAINER_HOME)/data/...)" >&2; exit 2; }
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) $(PIPELINE_ROOT)/scripts/validate_bag.py --bag "$(BAG)" --dataset "$(DATASET)"

run: ## Run a headless bag pipeline; optional compatible HYDRA_CONFIG/LABELS_CONFIG
	@test -n "$(BAG)" || { echo "BAG is required (container path, normally $(CONTAINER_HOME)/data/...)" >&2; exit 2; }
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) $(PIPELINE_ROOT)/scripts/run_pipeline.sh --dataset "$(DATASET)" --bag "$(BAG)" $(if $(HYDRA_CONFIG),--hydra-config "$(HYDRA_CONFIG)",) $(if $(LABELS_CONFIG),--labels-config "$(LABELS_CONFIG)",) $(RUN_ARGS)

inspect: ## Inspect DSG=/home/spark/output/.../dsg.json
	@test -n "$(DSG)" || { echo "DSG is required (container path, normally $(CONTAINER_HOME)/output/...)" >&2; exit 2; }
	@$(COMPOSE) --profile core run --rm core python3 $(PIPELINE_ROOT)/scripts/inspect_dsg.py "$(DSG)" $(INSPECT_ARGS)

rviz: ## Visualize live or DSG=...; optionally set VISUALIZATION_PROFILE=...
	@$(COMPOSE) --profile rviz run --rm rviz \
		$(PIPELINE_ROOT)/scripts/run_visualization.sh \
		$(if $(VISUALIZATION_PROFILE),,--dataset "$(DATASET)") \
		$(if $(VISUALIZATION_PROFILE),--profile "$(VISUALIZATION_PROFILE)",) \
		$(if $(DSG),--dsg "$(DSG)",)

gpu-smoke: ## Check the pinned GPU stack and load the downloaded YOLOE model
	@$(COMPOSE) --profile gpu run --rm pipeline \
		$(PIPELINE_ROOT)/scripts/gpu_smoke_test.sh

test: ## Run repository tests inside the development image
	@$(COMPOSE) --profile dev run --rm --build core-dev $(PIPELINE_ROOT)/scripts/run_tests.sh

lint: ## Run static repository checks inside the development image
	@$(COMPOSE) --profile dev run --rm --build core-dev $(PIPELINE_ROOT)/scripts/run_lint.sh

lock-dependencies: ## Resolve branch manifest to exact SHAs (maintainer command)
	@$(COMPOSE) --profile dev run --rm --build -v "$(CURDIR)/dependencies:$(PIPELINE_ROOT)/dependencies" core-dev $(PIPELINE_ROOT)/scripts/lock_dependencies.sh

clean: ## Remove local build/test products (never data, models, or output)
	@$(COMPOSE) down --remove-orphans
	@find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
