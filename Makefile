# Values are exported as data, never expanded into shell commands or sourced.
.DEFAULT_GOAL := help
SHELL := /bin/sh
OPERATOR_VARIABLES := ENV SECRETS_FILE MASTER_PUBLIC_KEY_FILE MASTER_PRIVATE_KEY_FILE WORKER_PUBLIC_KEY_FILE WORKER_PRIVATE_KEY_FILE MANAGEMENT_PUBLIC_KEY_FILE DRY_RUN OPERATOR_DIR STATE_REVIEWED CONFIRM REVIEWED_SHA POOL COUNT CURRENT_COUNT REDUCTION_REVIEWED REPLACEMENTS_REVIEWED KUBE_CONTEXT GITOPS_REVIEWED IMAGE REGISTRY TAG API_URL LIVE_REVIEWED
$(foreach variable,$(OPERATOR_VARIABLES),$(if $(filter undefined,$(origin $(variable))),,$(eval export $(variable))))

.PHONY: help doctor config-check cluster-init cluster-plan cluster-up cluster-scale flux-check flux-bootstrap images-build images-push status verify verify-live
help: ## Show commands; the default never deploys
	@python3 -B scripts/ops.py help
doctor: ## Check local tools and versions without contacting services
	@python3 -B scripts/ops.py doctor
config-check: ## Validate ENV and existing local input files
	@python3 -B scripts/ops.py config-check
cluster-init: ## Initialize the selected root; STATE_REVIEWED=1 required
	@python3 -B scripts/ops.py cluster-init
cluster-plan: ## Save a private plan; DRY_RUN=1 previews command only
	@python3 -B scripts/ops.py cluster-plan
cluster-up: ## Apply saved plan with REVIEWED_SHA and CONFIRM=apply-dev
	@python3 -B scripts/ops.py cluster-up
cluster-scale: ## Plan a persisted worker count change; never auto-apply
	@python3 -B scripts/ops.py cluster-scale
flux-check: ## Read-only readiness checks using explicit KUBE_CONTEXT
	@python3 -B scripts/ops.py flux-check
flux-bootstrap: ## Attach existing manifests to a prepared Flux operator
	@python3 -B scripts/ops.py flux-bootstrap
images-build: ## Build checked-in image to local OCI archive, both architectures
	@python3 -B scripts/ops.py images-build
images-push: ## Build and publish versioned image; CONFIRM=push required
	@python3 -B scripts/ops.py images-push
status: ## Summarize cluster/Flux health without printing resource contents
	@python3 -B scripts/ops.py status
verify: ## Offline tests, syntax, formatting, Kustomize and link checks
	@python3 -B scripts/ops.py verify
verify-live: ## Explicitly gated dev GET /ping and /ready; no ingestion
	@python3 -B scripts/ops.py verify-live
