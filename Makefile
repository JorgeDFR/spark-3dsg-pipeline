SHELL := /bin/bash
.DEFAULT_GOAL := help

PROFILE ?= core
DATASET ?= spot
MAPPING ?=
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
SOURCE ?= generic_rgbd
PREPROCESSOR ?= rtabmap_rgbd
INPUT ?=
PREPROCESS_OUTPUT ?=
PREPROCESS_ARGS ?=
PREPROCESS_DATA_ARGS ?=
PREPROCESS_TEST_ARGS ?=

ifeq ($(PROFILE),core)
SERVICE := core
else ifeq ($(PROFILE),gpu)
SERVICE := pipeline
else
$(error PROFILE must be core or gpu)
endif

.PHONY: help build build-preprocess models prepare-data prepare-preprocess-data test-preprocess shell preprocess-shell validate-source preprocess dev-shell validate-bag run inspect rviz gpu-smoke test lint clean config lock-dependencies

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target> [PROFILE=core|gpu] [DATASET=...] [MAPPING=...] [VAR=value]\n\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

config: ## Validate the resolved Compose configuration
	@$(COMPOSE) config --quiet

build: ## Build the exact-SHA v1 snapshot with PROFILE=core|gpu
ifeq ($(PROFILE),core)
	@$(COMPOSE) --profile core build core
else ifeq ($(PROFILE),gpu)
	@$(COMPOSE) --profile gpu build pipeline
endif

build-preprocess: ## Build the single exact-SHA RGB-D preprocessing toolbox image
	@$(COMPOSE) --profile preprocess build preprocess

preprocess-shell: ## Open a shell in the preprocessing toolbox image
	@$(COMPOSE) --profile preprocess run --rm preprocess bash

validate-source: ## Validate raw INPUT against SOURCE and PREPROCESSOR profiles
	@test -n "$(INPUT)" || { echo "INPUT is required (container path under $(CONTAINER_HOME)/data/raw)" >&2; exit 2; }
	@$(COMPOSE) --profile preprocess run --rm preprocess \
		python3 $(PIPELINE_ROOT)/scripts/python/validate_source.py --input "$(INPUT)" \
		--source "$(SOURCE)" --preprocessor "$(PREPROCESSOR)"

preprocess: ## Normalize INPUT into PREPROCESS_OUTPUT with one selectable pose backend
	@test -n "$(INPUT)" || { echo "INPUT is required (container path under $(CONTAINER_HOME)/data/raw)" >&2; exit 2; }
	@test -n "$(PREPROCESS_OUTPUT)" || { echo "PREPROCESS_OUTPUT is required (normally $(CONTAINER_HOME)/data/normalized/...) and must not already exist" >&2; exit 2; }
	@$(COMPOSE) --profile preprocess run --rm preprocess \
		python3 $(PIPELINE_ROOT)/scripts/python/preprocess_bag.py --input "$(INPUT)" \
		--output "$(PREPROCESS_OUTPUT)" --source "$(SOURCE)" \
		--preprocessor "$(PREPROCESSOR)" $(PREPROCESS_ARGS)

models: ## Download/checksum closed-set and YOLOE weights into the model mount
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) $(PIPELINE_ROOT)/scripts/shell/download_models.sh $(PROFILE)

prepare-data: ## Detect/extract/convert known Spot and uHumans2 example bags
	@$(COMPOSE) --profile tools run --rm --build data-setup \
		python3 $(PIPELINE_ROOT)/scripts/python/prepare_example_bags.py $(PREPARE_ARGS)

prepare-preprocess-data: ## Download and convert compact public preprocessing fixtures
	@$(COMPOSE) --profile preprocess run --rm preprocess \
		python3 $(PIPELINE_ROOT)/scripts/python/prepare_preprocessing_datasets.py $(PREPROCESS_DATA_ARGS)

test-preprocess: ## Run public-data preprocessing integration tests through Docker
	@python3 scripts/python/run_preprocessing_tests.py $(PREPROCESS_TEST_ARGS)

shell: ## Open an interactive shell in the selected image
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) bash

dev-shell: ## Open the compiler/source development image
	@$(COMPOSE) --profile dev run --rm --build core-dev bash

validate-bag: ## Validate BAG against the DATASET + MAPPING input contract
	@test -n "$(BAG)" || { echo "BAG is required (container path, normally $(CONTAINER_HOME)/data/normalized/...)" >&2; exit 2; }
	@test -n "$(MAPPING)" || { echo "MAPPING is required (recorded, closed_set, or open_set)" >&2; exit 2; }
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) python3 $(PIPELINE_ROOT)/scripts/python/validate_bag.py --bag "$(BAG)" --dataset "$(DATASET)" --mapping "$(MAPPING)"

run: ## Run DATASET with MAPPING=recorded|closed_set|open_set
	@test -n "$(BAG)" || { echo "BAG is required (container path, normally $(CONTAINER_HOME)/data/normalized/...)" >&2; exit 2; }
	@test -n "$(MAPPING)" || { echo "MAPPING is required (recorded, closed_set, or open_set)" >&2; exit 2; }
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) $(PIPELINE_ROOT)/scripts/shell/run_pipeline.sh --dataset "$(DATASET)" --mapping "$(MAPPING)" --bag "$(BAG)" $(if $(HYDRA_CONFIG),--hydra-config "$(HYDRA_CONFIG)",) $(if $(LABELS_CONFIG),--labels-config "$(LABELS_CONFIG)",) $(RUN_ARGS)

inspect: ## Inspect DSG=/home/spark/output/.../dsg.json
	@test -n "$(DSG)" || { echo "DSG is required (container path, normally $(CONTAINER_HOME)/output/...)" >&2; exit 2; }
	@$(COMPOSE) --profile core run --rm core python3 $(PIPELINE_ROOT)/scripts/python/inspect_dsg.py "$(DSG)" $(INSPECT_ARGS)

rviz: ## Visualize a live MAPPING or DSG=... with VISUALIZATION_PROFILE=...
	@$(COMPOSE) --profile rviz run --rm rviz \
		$(PIPELINE_ROOT)/scripts/shell/run_visualization.sh \
		$(if $(MAPPING),--dataset "$(DATASET)" --mapping "$(MAPPING)",$(if $(DSG),,--dataset "$(DATASET)")) \
		$(if $(VISUALIZATION_PROFILE),--profile "$(VISUALIZATION_PROFILE)",) \
		$(if $(DSG),--dsg "$(DSG)",)

gpu-smoke: ## Check the pinned GPU stack and load the downloaded YOLOE model
	@$(COMPOSE) --profile gpu run --rm pipeline \
		$(PIPELINE_ROOT)/scripts/shell/gpu_smoke_test.sh

test: ## Run repository tests inside the development image
	@$(COMPOSE) --profile dev run --rm --build core-dev $(PIPELINE_ROOT)/scripts/shell/run_tests.sh

lint: ## Run static repository checks inside the development image
	@$(COMPOSE) --profile dev run --rm --build core-dev $(PIPELINE_ROOT)/scripts/shell/run_lint.sh

lock-dependencies: ## Resolve branch manifest to exact SHAs (maintainer command)
	@$(COMPOSE) --profile dev run --rm --build -v "$(CURDIR)/dependencies:$(PIPELINE_ROOT)/dependencies" core-dev $(PIPELINE_ROOT)/scripts/shell/lock_dependencies.sh

clean: ## Remove local build/test products (never data, models, or output)
	@$(COMPOSE) down --remove-orphans
	@find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
