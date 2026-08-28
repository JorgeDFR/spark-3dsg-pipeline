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

ifeq ($(PROFILE),core)
SERVICE := core
else ifeq ($(PROFILE),gpu)
SERVICE := pipeline
else ifeq ($(PROFILE),daaam)
SERVICE := daaam
else
$(error PROFILE must be core, gpu, or daaam)
endif

.PHONY: help build models prepare-data shell validate-bag run inspect rviz test lint clean config lock-dependencies

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target> [PROFILE=core|gpu] [VAR=value]\n\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

config: ## Validate the resolved Compose configuration
	@$(COMPOSE) config --quiet

build: ## Build PROFILE=core|gpu (DAAAM is a post-v1 placeholder)
ifeq ($(PROFILE),core)
	@$(COMPOSE) --profile core build core
else ifeq ($(PROFILE),gpu)
	@$(COMPOSE) --profile core build core
	@$(COMPOSE) --profile gpu build pipeline
else
	@echo "DAAAM is intentionally outside the v1 lock; see docs/DAAAM.md" >&2
	@exit 2
endif

models: ## Download and checksum external model weights into the mounted model directory
ifeq ($(PROFILE),daaam)
	@echo "DAAAM model management is not implemented in v1; see docs/DAAAM.md" >&2
	@exit 2
else
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) $(PIPELINE_ROOT)/scripts/download_models.sh $(PROFILE)
endif

prepare-data: ## Detect/extract/convert known Spot and uHumans2 example bags
	@$(COMPOSE) --profile tools run --rm --build data-setup \
		$(PIPELINE_ROOT)/scripts/prepare_example_bags.py $(PREPARE_ARGS)

shell: ## Open an interactive shell in the selected image
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) bash

validate-bag: ## Validate BAG against DATASET before mapping
	@test -n "$(BAG)" || { echo "BAG is required (container path, normally $(CONTAINER_HOME)/data/...)" >&2; exit 2; }
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) $(PIPELINE_ROOT)/scripts/validate_bag.py --bag "$(BAG)" --dataset "$(DATASET)"

run: ## Run a headless bag pipeline; requires BAG=/home/spark/data/...
	@test -n "$(BAG)" || { echo "BAG is required (container path, normally $(CONTAINER_HOME)/data/...)" >&2; exit 2; }
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) $(PIPELINE_ROOT)/scripts/run_pipeline.sh --dataset "$(DATASET)" --bag "$(BAG)" $(RUN_ARGS)

inspect: ## Inspect DSG=/home/spark/output/.../dsg.json
	@test -n "$(DSG)" || { echo "DSG is required (container path, normally $(CONTAINER_HOME)/output/...)" >&2; exit 2; }
	@$(COMPOSE) --profile core run --rm core python3 $(PIPELINE_ROOT)/scripts/inspect_dsg.py "$(DSG)" $(INSPECT_ARGS)

rviz: ## Start optional RViz with the scene-graph configuration
	@$(COMPOSE) --profile rviz run --rm rviz \
		$(PIPELINE_ROOT)/scripts/run_visualization.sh "$(DATASET)"

test: ## Run repository tests inside the core image
	@$(COMPOSE) --profile core run --rm core $(PIPELINE_ROOT)/scripts/run_tests.sh

lint: ## Run static repository checks inside the core image
	@$(COMPOSE) --profile core run --rm core $(PIPELINE_ROOT)/scripts/run_lint.sh

lock-dependencies: ## Resolve branch manifest to exact SHAs (maintainer command)
	@$(COMPOSE) --profile core run --rm -v "$(CURDIR)/dependencies:$(PIPELINE_ROOT)/dependencies" core $(PIPELINE_ROOT)/scripts/lock_dependencies.sh

clean: ## Remove local build/test products (never data, models, or output)
	@$(COMPOSE) down --remove-orphans
	@find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
