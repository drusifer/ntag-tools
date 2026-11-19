# ntag-tools: tag validator + provisioner + key packages, one product, one version.
ifneq ("$(wildcard .venv/bin/python)","")
PYTHON ?= .venv/bin/python
else
PYTHON ?= python3
endif

VERSION_FILE := $(shell cat VERSION)
IMAGE_VERSION ?= latest
PCSC_STUB := $(shell $(PYTHON) -c "import smartcard" 2>/dev/null || echo $(CURDIR)/tools/pcsc_stub)
export PYTHONPATH := $(CURDIR)/shared/src:$(CURDIR)/ntag_keys/src:$(CURDIR)/tag_validator_service/src:$(CURDIR)/sdm_provisioner/src$(if $(PCSC_STUB),:$(PCSC_STUB))$(if $(PYTHONPATH),:$(PYTHONPATH))

.DEFAULT_GOAL := help
PACKAGES := $(wildcard shared ntag_keys tag_validator_service sdm_provisioner)

.PHONY: help venv test-all test-shared test-ntag-keys test-tag-validator test-sdm-provisioner test-e2e lint check-versions dist clean
help: ## Show available make targets
	@$(PYTHON) -c "import re; [print(f'    {m.group(1):<30} {m.group(2)}') for line in open('Makefile', encoding='utf-8') if (m := re.match(r'^([a-zA-Z0-9_-]+):.*?## (.*)$$', line))]"

venv: ## Create .venv with all dev dependencies (pyscard needs system PC/SC headers; install it separately)
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install pytest pytest-cov pytest-asyncio ruff cryptography pycryptodome coolname pillow textual kubernetes gunicorn build

test-all: test-shared test-ntag-keys test-tag-validator test-sdm-provisioner test-e2e ## Run every test suite

test-shared: ## Tests for shared
	$(PYTHON) -m pytest shared/tests -q

test-ntag-keys: ## Tests for ntag_keys
	$(PYTHON) -m pytest ntag_keys/tests -q

test-tag-validator: ## Tests for tag_validator_service
	$(PYTHON) -m pytest tag_validator_service/tests -q

test-sdm-provisioner: ## Tests for sdm_provisioner
	$(PYTHON) -m pytest sdm_provisioner/tests -q

test-e2e: ## Provision -> publish -> validate end-to-end tests
	$(PYTHON) -m pytest tests/e2e -q

lint: ## Ruff over every package
	$(PYTHON) -m ruff check shared ntag_keys tag_validator_service sdm_provisioner/src/sdm_provisioner/store_key_manager.py sdm_provisioner/tests/test_store_key_manager.py tests

check-versions: ## Fail if any package version differs from VERSION
	@$(PYTHON) -c "import re,sys,pathlib; v=pathlib.Path('VERSION').read_text().strip(); bad=[(p,m.group(1)) for p in '$(PACKAGES)'.split() if (m:=re.search(r'^version\s*=\s*\"([^\"]+)\"', pathlib.Path(p,'pyproject.toml').read_text(), re.M)) and m.group(1)!=v]; print('versions ok: '+v) if not bad else (print('version mismatch vs '+v+': '+str(bad)), sys.exit(1))"

# Wheels are byte-reproducible: timestamps come from the commit, not the clock.
dist: check-versions ## Build reproducible wheels for every package into dist/
	@mkdir -p dist
	@for p in $(PACKAGES); do SOURCE_DATE_EPOCH=$$(git log -1 --format=%ct) $(PYTHON) -m build --wheel --outdir dist $$p || exit 1; done

clean: ## Remove build artifacts
	rm -rf dist build
	find . -name __pycache__ -not -path './.venv/*' -prune -exec rm -rf {} +

# Validator container (moved from GlobalHeadsOrTails)
.PHONY: pkg-tag-validator verify-tag-validator-container export-tag-validator-image deploy-forgejo
pkg-tag-validator: ## Build the validator container image
	$(MAKE) -C tag_validator_service pkg VERSION=$(IMAGE_VERSION)

verify-tag-validator-container: ## Boot-check the validator container read-only
	$(MAKE) -C tag_validator_service verify-container VERSION=$(IMAGE_VERSION)

export-tag-validator-image: ## Build, verify and export dist/tag-validator-service-$(IMAGE_VERSION).tar
	$(MAKE) -C tag_validator_service export-image VERSION=$(IMAGE_VERSION)
	@mkdir -p dist
	@cp -f tag_validator_service/dist/tag-validator-service-$(IMAGE_VERSION).tar dist/

PI_PATCH        ?= $(HOME)/Projects/pi-patch
FORGEJO_PUBLISH := $(PI_PATCH)/cluster/scripts/forgejo-publish.sh
FORGEJO_VERSION ?= $(shell git describe --tags --always)

deploy-forgejo: export-tag-validator-image dist ## Publish validator image + wheels to the pi-patch Forgejo
	$(FORGEJO_PUBLISH) image dist/tag-validator-service-$(IMAGE_VERSION).tar tag-validator-service $(FORGEJO_VERSION)
	$(FORGEJO_PUBLISH) pypi dist
