SHELL := /bin/bash
.DEFAULT_GOAL := help

PROFILE ?= core
BUILD ?= 0
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
ROS2_BAG ?=

ifeq ($(filter $(PROFILE),core gpu preprocess all),)
$(error PROFILE must be core, gpu, preprocess, or all (build only))
endif
SERVICE := $(PROFILE)

.PHONY: help check-compose build download-models prepare-data prepare-preprocess-fixtures test-preprocess shell convert-ros1 validate-source preprocess validate-bag run inspect rviz check-gpu test lint clean lock-dependencies

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target> [PROFILE=core|gpu|preprocess] [DATASET=...] [MAPPING=...] [VAR=value]\n\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-28s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build PROFILE=core|gpu|preprocess|all images (default: core)
ifeq ($(PROFILE),core)
	@$(COMPOSE) --profile core build core
else ifeq ($(PROFILE),gpu)
	@$(COMPOSE) --profile gpu build gpu
else ifeq ($(PROFILE),preprocess)
	@$(COMPOSE) --profile preprocess build preprocess
else ifeq ($(PROFILE),all)
	@$(COMPOSE) --profile core --profile gpu --profile preprocess build core gpu preprocess
endif

run: ## Run DATASET with MAPPING=recorded|closed_set|open_set
	@test "$(PROFILE)" = core -o "$(PROFILE)" = gpu || { echo "PROFILE must be core or gpu for run" >&2; exit 2; }
	@test -n "$(BAG)" || { echo "BAG is required (container path, normally $(CONTAINER_HOME)/data/normalized/...)" >&2; exit 2; }
	@test -n "$(MAPPING)" || { echo "MAPPING is required (recorded, closed_set, or open_set)" >&2; exit 2; }
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) $(PIPELINE_ROOT)/scripts/shell/run_pipeline.sh --dataset "$(DATASET)" --mapping "$(MAPPING)" --bag "$(BAG)" $(if $(HYDRA_CONFIG),--hydra-config "$(HYDRA_CONFIG)",) $(if $(LABELS_CONFIG),--labels-config "$(LABELS_CONFIG)",) $(RUN_ARGS)

rviz: ## Visualize a live MAPPING or DSG=... with VISUALIZATION_PROFILE=...
	@$(COMPOSE) --profile rviz run --rm rviz \
		$(PIPELINE_ROOT)/scripts/shell/run_visualization.sh \
		$(if $(MAPPING),--dataset "$(DATASET)" --mapping "$(MAPPING)",$(if $(DSG),,--dataset "$(DATASET)")) \
		$(if $(VISUALIZATION_PROFILE),--profile "$(VISUALIZATION_PROFILE)",) \
		$(if $(DSG),--dsg "$(DSG)",)

preprocess: ## Normalize INPUT into PREPROCESS_OUTPUT with one selectable pose backend
	@test -n "$(INPUT)" || { echo "INPUT is required (container path under $(CONTAINER_HOME)/data/raw)" >&2; exit 2; }
	@test -n "$(PREPROCESS_OUTPUT)" || { echo "PREPROCESS_OUTPUT is required (normally $(CONTAINER_HOME)/data/normalized/...) and must not already exist" >&2; exit 2; }
	@$(COMPOSE) --profile preprocess run --rm preprocess \
		python3 $(PIPELINE_ROOT)/scripts/python/preprocess_bag.py --input "$(INPUT)" \
		--output "$(PREPROCESS_OUTPUT)" --source "$(SOURCE)" \
		--preprocessor "$(PREPROCESSOR)" $(PREPROCESS_ARGS)

validate-bag: ## Validate BAG against the DATASET + MAPPING input contract
	@test "$(PROFILE)" = core -o "$(PROFILE)" = gpu || { echo "PROFILE must be core or gpu for validate-bag" >&2; exit 2; }
	@test -n "$(BAG)" || { echo "BAG is required (container path, normally $(CONTAINER_HOME)/data/normalized/...)" >&2; exit 2; }
	@test -n "$(MAPPING)" || { echo "MAPPING is required (recorded, closed_set, or open_set)" >&2; exit 2; }
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) python3 $(PIPELINE_ROOT)/scripts/python/validate_bag.py --bag "$(BAG)" --dataset "$(DATASET)" --mapping "$(MAPPING)"

validate-source: ## Validate raw INPUT against SOURCE and PREPROCESSOR profiles
	@test -n "$(INPUT)" || { echo "INPUT is required (container path under $(CONTAINER_HOME)/data/raw)" >&2; exit 2; }
	@$(COMPOSE) --profile preprocess run --rm preprocess \
		python3 $(PIPELINE_ROOT)/scripts/python/validate_source.py --input "$(INPUT)" \
		--source "$(SOURCE)" --preprocessor "$(PREPROCESSOR)"

convert-ros1: ## Convert INPUT ROS 1 bag to ROS2_BAG in the raw data directory
	@test -n "$(INPUT)" || { echo "INPUT is required (container path to a ROS 1 .bag file)" >&2; exit 2; }
	@test -n "$(ROS2_BAG)" || { echo "ROS2_BAG is required (container path for a new ROS 2 bag directory)" >&2; exit 2; }
	@$(COMPOSE) --profile preprocess run --rm preprocess \
		rosbags-convert --src "$(INPUT)" --dst "$(ROS2_BAG)"

inspect: ## Inspect DSG=/home/spark/output/.../dsg.json
	@test -n "$(DSG)" || { echo "DSG is required (container path, normally $(CONTAINER_HOME)/output/...)" >&2; exit 2; }
	@$(COMPOSE) --profile core run --rm core python3 $(PIPELINE_ROOT)/scripts/python/inspect_dsg.py "$(DSG)" $(INSPECT_ARGS)

download-models: ## Download/checksum GPU model weights into the model mount
	@$(COMPOSE) --profile gpu run --rm gpu $(PIPELINE_ROOT)/scripts/shell/download_models.sh gpu

prepare-data: ## Detect/extract/convert known Spot and uHumans2 example bags
	@$(COMPOSE) --profile tools run --rm --build data-setup \
		python3 $(PIPELINE_ROOT)/scripts/python/prepare_example_bags.py $(PREPARE_ARGS)

prepare-preprocess-fixtures: ## Download and convert public preprocessing test fixtures
	@$(COMPOSE) --profile preprocess run --rm preprocess \
		python3 $(PIPELINE_ROOT)/scripts/python/prepare_preprocessing_datasets.py $(PREPROCESS_DATA_ARGS)

shell: ## Open PROFILE=core|gpu|preprocess shell (BUILD=1 rebuilds first)
	@test "$(PROFILE)" != all || { echo "PROFILE=all is only supported by build" >&2; exit 2; }
	@test "$(BUILD)" = 0 -o "$(BUILD)" = 1 || { echo "BUILD must be 0 or 1" >&2; exit 2; }
	@$(COMPOSE) --profile $(PROFILE) run --rm $(if $(filter 1,$(BUILD)),--build,) $(SERVICE) bash

check-compose: ## Validate the resolved Compose configuration
	@$(COMPOSE) config --quiet

check-gpu: ## Check the pinned GPU stack and load the downloaded YOLOE model
	@$(COMPOSE) --profile gpu run --rm gpu \
		$(PIPELINE_ROOT)/scripts/shell/gpu_smoke_test.sh

test: ## Run repository tests inside the development image
	@$(COMPOSE) --profile core run --rm --build core $(PIPELINE_ROOT)/scripts/shell/run_tests.sh

test-preprocess: ## Run public-data preprocessing integration tests through Docker
	@python3 scripts/python/run_preprocessing_tests.py $(PREPROCESS_TEST_ARGS)

lint: ## Run static repository checks inside the development image
	@$(COMPOSE) --profile core run --rm --build core $(PIPELINE_ROOT)/scripts/shell/run_lint.sh

lock-dependencies: ## Resolve branch manifest to exact SHAs (maintainer command)
	@$(COMPOSE) --profile core run --rm --build -v "$(CURDIR)/dependencies:$(PIPELINE_ROOT)/dependencies" core $(PIPELINE_ROOT)/scripts/shell/lock_dependencies.sh

clean: ## Remove local build/test products (never data, models, or output)
	@$(COMPOSE) down --remove-orphans
	@find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
