# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A minimal but complete **LLMOps Quickstart** for Databricks. Demonstrates the full lifecycle of an LLM-powered application: data ingestion → agent build → evaluation → deployment → inference.

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
   databricks bundle deploy -v catalog_name=my_catalog -v llm_endpoint=databricks-meta-llama-3-3-70b-instruct
   ```

3. **Deploy and run**:
   ```bash
   databricks bundle deploy
   databricks bundle run data_preprocessing_job
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
databricks bundle run data_preprocessing_job
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
notebooks/
  1_data_preprocessing/
    data_ingestion.py         # Creates support_tickets Delta table
  2_model_build_and_deploy/
    quickstart_agent.py       # ChatAgent definition (logged as MLflow model artifact)
    model_config.yml          # Default model config (llm_endpoint); overridden at log time
    model_build.py            # Logs agent to MLflow, passes run_id downstream
    model_evaluation.py       # Loads agent, runs predictions, logs accuracy; promotes to Champion
    model_deployment.py       # Deploys Champion to Mosaic AI Model Serving via agents.deploy()
  3_inference/
    batch_inference.py        # Loads Champion, runs over all tickets, writes inference_results
    realtime_inference.py     # Queries the serving endpoint via OpenAI-compatible API
resources/
  model_artifacts.yml         # UC schema + MLflow experiment
  1_data_preprocessing_job.yml
  2_1_model_build_evaluation_job.yml
  2_2_model_deployment_job.yml
  3_batch_inference_job.yml
databricks.yml                # Bundle targets (dev/prod) + variables — no hard-coded host or catalog
```

### Key design decisions

- **No hard-coded workspace host** — `databricks.yml` omits `workspace.host`; the CLI profile or `--profile` flag supplies it, making the bundle portable across workspaces.
- **`catalog_name` defaults to `main`** — present in every Databricks workspace. Override with `-v catalog_name=...`.
- **`llm_endpoint` is a bundle variable** — flows from `databricks.yml` → job parameter → `model_build.py` → `mlflow.pyfunc.log_model(model_config=...)`. The agent reads it at serving time via `mlflow.models.ModelConfig`.
- **`model_config.yml`** lives alongside `quickstart_agent.py` for interactive/dev use; at log time the value is baked into the MLflow artifact so the serving endpoint uses the correct endpoint.
- **`quickstart_agent.py`** lives alongside the build notebook so `python_model="quickstart_agent.py"` resolves correctly as a relative path at log time.
- **Serverless Environment v5** is forced in every job resource via `environments[].spec.environment_version: "5"`. This provides `mlflow`, `databricks-agents`, `databricks-sdk`, and `pydantic 2.10.6` pre-installed. Only `databricks-openai` (not in v5) is added as a dependency.
- **No `%pip install`** in any notebook — all dependencies come from the job environment spec.
- **Champion alias** gates deployment: `model_evaluation.py` only sets the `Champion` alias if `eval/accuracy >= accuracy_threshold` (default 0.8). `model_deployment.py` always deploys whatever version carries the `Champion` alias.
- **Task values** pass `logged_run_id` from `model_build` → `model_evaluation` via `dbutils.jobs.taskValues`.
- **Schema creation** is handled both by the bundle (`model_artifacts.yml` schema resource) and defensively in `data_ingestion.py` (`CREATE SCHEMA IF NOT EXISTS`).
