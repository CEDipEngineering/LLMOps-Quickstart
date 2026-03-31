# LLMOps Quickstart for Databricks

A minimal but complete end-to-end LLMOps example on Databricks, designed for **regulated industries** where developers are constrained to only interact with the core agent — not the automation pipelines, evaluation workflows, or deployment infrastructure.

**Data Ingestion → Agent Build → Evaluation → Deployment → Inference**

Use case: a **customer support ticket classifier** that uses a Databricks Foundation Model to categorize free-text tickets into `billing`, `technical_issue`, `feature_request`, `account_management`, or `other`.

---

## Prerequisites

- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) v0.200+
- A Databricks workspace with:
  - Unity Catalog enabled
  - Foundation Model APIs enabled (for the default `databricks-claude-sonnet-4-6` endpoint)
  - Permissions to create schemas, registered models, jobs, and Model Serving endpoints

---

## Quickstart

### 1. Authenticate

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com
```

Or configure a named profile:

```bash
databricks configure --profile my-profile
```

### 2. Clone and deploy

```bash
git clone https://github.com/CEDipEngineering/LLMOps-Quickstart.git
cd LLMOps-Quickstart

databricks bundle deploy
```

This creates the Unity Catalog schema, MLflow experiment, and all jobs in your workspace under your user directory.

> **Using a named profile?** Prefix all commands with `--profile my-profile`.

### 3. Run the pipeline

Run each job in order:

```bash
# Step 1 — ingest evaluation dataset into a Delta table
databricks bundle run data_ingestion_job

# Step 2 — build and evaluate the classifier; promote to Champion if accuracy >= 80%
databricks bundle run model_build_evaluation_job

# Step 3 — deploy the Champion model to a Model Serving endpoint
databricks bundle run model_deployment_job

# Step 4 — run batch inference over the input table
databricks bundle run batch_inference_job
```

---

## Configuration

### Bundle variables

Infrastructure-level settings exposed as bundle variables with sensible defaults:

| Variable | Default | Description |
|---|---|---|
| `catalog_name` | `main` | Unity Catalog catalog (must already exist) |
| `schema_name` | `llmops_quickstart` | UC schema (created by the bundle) |
| `model_name` | `support_ticket_classifier` | Registered model name |
| `llm_endpoint` | `databricks-claude-sonnet-4-6` | Foundation Model API endpoint used by the agent |

Override variables at deploy time:

```bash
databricks bundle deploy \
  -v catalog_name=my_catalog \
  -v llm_endpoint=databricks-meta-llama-3-3-70b-instruct
```

### Agent configuration

Agent-specific settings live in [`developer/agent_config.yml`](developer/agent_config.yml) — the interface contract between the developer and platform zones. See the file for full documentation.

### Production target

```bash
databricks bundle deploy --target prod
databricks bundle run --target prod data_ingestion_job
# ... etc.
```

The `prod` target uses `llmops_quickstart_prod` as the schema name.

---

## Project Structure

The project enforces a clear separation between **developer-owned** and **platform-owned** code:

```
developer/                        ← DEVELOPERS EDIT HERE ONLY
  agent_config.yml                  Interface contract (agent path, eval schema, thresholds)
  agent/
    agent.py                        MLflow ChatAgent definition
    model_config.yml                Default agent config for local dev (llm_endpoint)
  eval/
    eval_data.py                    Evaluation dataset notebook (standardized schema)

platform/                         ← DEVELOPERS DO NOT TOUCH
  pipelines/
    model_build.py                  Generic: reads agent path + config from agent_config.yml
    model_evaluation.py             Generic: uses input/expected_output contract
    model_deployment.py             Deploys Champion to Mosaic AI Model Serving
    batch_inference.py              Generic: reads table/column names from agent_config.yml
    realtime_inference.py           Queries serving endpoint via OpenAI-compatible API
  resources/
    model_artifacts.yml             UC schema + MLflow experiment resources
    1_data_ingestion_job.yml
    2_1_model_build_evaluation_job.yml
    2_2_model_deployment_job.yml
    3_batch_inference_job.yml

databricks.yml                    Bundle entry point — targets, variables
```

### Developer workflow

Developers only need to:

1. **Define their agent** in `developer/agent/agent.py` (must extend MLflow `ChatAgent`)
2. **Provide evaluation data** in `developer/eval/eval_data.py` (must write a table with `input` and `expected_output` columns)
3. **Configure the contract** in `developer/agent_config.yml` (agent file path, eval schema, thresholds)
4. **Deploy and run** the standard pipeline commands

---

## How It Works

1. **Data Ingestion** — The developer-owned `eval_data.py` notebook writes labelled evaluation data to a Delta table with standardized `input` and `expected_output` columns.
2. **Model Build** — The platform reads `agent_config.yml` to locate the agent file, then logs it as an MLflow `ChatAgent` model. The configured LLM endpoint is baked into the model artifact via `mlflow.models.ModelConfig`.
3. **Evaluation** — The platform loads the logged agent and runs predictions against the evaluation dataset. If accuracy meets the threshold defined in `agent_config.yml` (default 80%), the model is registered in Unity Catalog and aliased as **Champion**.
4. **Deployment** — The Champion model version is deployed to a Mosaic AI Model Serving endpoint via `databricks.agents.deploy()`.
5. **Inference** — Batch inference reads the input table from `agent_config.yml` and writes predictions to the output table. Real-time inference queries the serving endpoint via the OpenAI-compatible API.
