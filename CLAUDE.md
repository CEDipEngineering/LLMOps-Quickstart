# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A minimal but complete **LLMOps Quickstart** for Databricks, designed for **regulated industries** where developers are constrained to only interact with the core agent — not the automation pipelines, evaluation workflows, or deployment infrastructure.

The project is split into two zones:
- **`developer/`** — developers edit only these files (agent code, eval data, config contract)
- **`platform/`** — ops-managed pipelines and job resources that developers never touch

Use case: **Customer support ticket classifier** — a `ChatAgent` that classifies free-text support tickets into five categories (`billing`, `technical_issue`, `feature_request`, `account_management`, `other`).

Reference repos: [MLOps Quickstart](https://github.com/databricks-solutions/mlops-quickstart), [e2e-llmops-project](https://github.com/brunotafurc/e2e-llmops-project).

## Setup for a New Workspace

1. **Authenticate** with the Databricks CLI:
   ```bash
   databricks auth login --host <your-workspace-url>
   # or with a named profile:
   databricks configure --profile <profile>
   ```

2. **Override variables** only if the defaults don't suit your workspace:

   | Variable | Default | Description |
   |---|---|---|
   | `catalog_name` | `main` | UC catalog — must already exist |
   | `schema_name` | `llmops_quickstart` | UC schema — created by the bundle |
   | `model_name` | `support_ticket_classifier` | Registered model name |
   | `llm_endpoint` | `databricks-claude-sonnet-4-6` | Foundation Model API endpoint |

   Override at deploy time:
   ```bash
   databricks bundle deploy --var="catalog_name=my_catalog" --var="llm_endpoint=databricks-meta-llama-3-3-70b-instruct"
   ```

3. **Deploy and run**:
   ```bash
   databricks bundle deploy
   databricks bundle run data_ingestion_job
   databricks bundle run model_build_evaluation_job
   databricks bundle run model_deployment_job
   databricks bundle run batch_inference_job
   ```

## Commands

```bash
# Validate bundle (dry-run, no changes deployed)
databricks bundle validate

# Deploy to dev (default target)
databricks bundle deploy

# Run jobs individually
databricks bundle run data_ingestion_job
databricks bundle run model_build_evaluation_job
databricks bundle run model_deployment_job
databricks bundle run batch_inference_job

# Deploy to prod
databricks bundle deploy --target prod

# With a named CLI profile
databricks --profile <profile> bundle deploy
```

## Architecture

```
developer/                        # ← DEVELOPERS EDIT HERE ONLY
  agent_config.yml                # Interface contract between developer/ and platform/
  agent/
    agent.py                      # ChatAgent definition (logged as MLflow model artifact)
  eval/
    eval_data.py                  # Evaluation dataset notebook (standardized schema)

platform/                         # ← DEVELOPERS DO NOT TOUCH
  pipelines/
    model_build.py                # Generic: reads agent path + config from agent_config.yml
    model_evaluation.py           # Generic: uses input/expected_output contract
    model_deployment.py           # Deploys Champion to Mosaic AI Model Serving
    batch_inference.py            # Generic: reads table/column names from agent_config.yml
    realtime_inference.py         # Queries the serving endpoint via OpenAI-compatible API
  resources/
    model_artifacts.yml           # UC schema + MLflow experiment
    1_data_ingestion_job.yml
    2_1_model_build_evaluation_job.yml
    2_2_model_deployment_job.yml
    3_batch_inference_job.yml

databricks.yml                    # Bundle targets (dev/prod) + variables
```

### Interface contract: `developer/agent_config.yml`

This YAML file is the single bridge between zones. The developer sets:
- **`agent.file`** — path to their ChatAgent python file (relative to `developer/`)
- **`agent.extra_pip_requirements`** — additional pip packages the agent needs
- **`llm_endpoint`** — the Foundation Model API endpoint (top-level key, read by the agent at dev time via `ModelConfig` and baked into the MLflow artifact at log time)
- **`eval`** — table name, column names (`input`, `expected_output`), and accuracy threshold
- **`inference`** — input/output table names and column names

Platform pipelines read this config at runtime via `yaml.safe_load()`.

### Key design decisions

- **Developer/platform separation** — developers only edit files in `developer/`. Platform pipelines in `platform/` are generic and work with any MLflow `ChatAgent`.
- **`agent_config.yml` as the interface** — single source of truth for agent-specific configuration. Platform notebooks read it at runtime, avoiding duplication of config values as bundle variables.
- **Standardized eval schema** — evaluation dataset must have `input` (agent input text) and `expected_output` (expected response) columns. Platform evaluation is use-case-agnostic.
- **Single source of truth for `llm_endpoint`** — `agent_config.yml` holds the default; the agent reads it at dev time via `ModelConfig(development_config=...)` and the platform bakes it into the MLflow artifact at log time. The bundle variable can override it per target.
- **`bundle_root` widget** — platform notebooks receive `${workspace.root_path}/files` as a job parameter to reliably resolve `agent_config.yml` in the workspace file system.
- **No hard-coded workspace host** — `databricks.yml` omits `workspace.host`; the CLI profile supplies it.
- **`catalog_name` defaults to `main`** — present in every Databricks workspace.
- **Serverless Environment v5** — all jobs use it. `pyyaml` is added where config parsing is needed. `databricks-openai` is added where agent interaction occurs.
- **No `%pip install`** in any notebook — all dependencies come from the job environment spec.
- **Champion alias** gates deployment: `model_evaluation.py` only sets the alias if accuracy >= threshold. `model_deployment.py` deploys whatever version carries the alias.
- **Task values** pass `logged_run_id` from `model_build` → `model_evaluation`.
- **Schema creation** is handled both by the bundle (`model_artifacts.yml`) and defensively in `eval_data.py`.
