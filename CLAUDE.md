# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A minimal but complete **LLMOps Quickstart** for Databricks. Demonstrates the full lifecycle of an LLM-powered application: data ingestion → agent build → evaluation → deployment → inference.

Use case: **Customer support ticket classifier** — a `ChatAgent` that classifies free-text support tickets into five categories (`billing`, `technical_issue`, `feature_request`, `account_management`, `other`).

Reference repos: [MLOps Quickstart](https://github.com/databricks-solutions/mlops-quickstart), [e2e-llmops-project](https://github.com/brunotafurc/e2e-llmops-project).

## Workspace

- **Profile**: `fevm` (Databricks CLI profile)
- **Host**: `https://fevm-cedip-fevm-aws-classic-stable.cloud.databricks.com`
- **Catalog**: `cedip_fevm_aws_classic_stable_catalog`
- **Schema**: `llmops_quickstart` (dev) / `llmops_quickstart_prod` (prod)

## Commands

```bash
# Validate bundle
databricks --profile fevm bundle validate

# Deploy to dev (default target)
databricks --profile fevm bundle deploy

# Run jobs individually
databricks --profile fevm bundle run data_preprocessing_job
databricks --profile fevm bundle run model_build_evaluation_job
databricks --profile fevm bundle run model_deployment_job
databricks --profile fevm bundle run batch_inference_job

# Deploy to prod
databricks --profile fevm bundle deploy --target prod
```

## Architecture

```
notebooks/
  1_data_preprocessing/
    data_ingestion.py         # Creates support_tickets Delta table
  2_model_build_and_deploy/
    quickstart_agent.py       # ChatAgent definition (also logged as MLflow model artifact)
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
databricks.yml                # Bundle targets (dev/prod) + variables
```

### Key design decisions

- **`quickstart_agent.py`** lives alongside the build notebook so `python_model="quickstart_agent.py"` resolves correctly as a relative path at log time.
- **Serverless Environment v5** is forced in every job resource via `environments[].spec.environment_version: "5"`. This provides `mlflow`, `databricks-agents`, `databricks-sdk`, and `pydantic 2.10.6` pre-installed. Only `databricks-openai` (not in v5) is added as a dependency.
- **No `%pip install`** in any notebook — all dependencies come from the job environment spec.
- **Champion alias** gates deployment: `model_evaluation.py` only sets the `Champion` alias if `eval/accuracy >= accuracy_threshold` (default 0.8). `model_deployment.py` always deploys whatever version carries the `Champion` alias.
- **Task values** pass `logged_run_id` from `model_build` → `model_evaluation` via `dbutils.jobs.taskValues`.
- The LLM endpoint used by the agent is `databricks-claude-sonnet-4-6`.
