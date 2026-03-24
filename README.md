# LLMOps Quickstart for Databricks

A minimal but complete end-to-end LLMOps example on Databricks, demonstrating the full lifecycle of an LLM-powered application:

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
# Step 1 — ingest sample support tickets into a Delta table
databricks bundle run data_preprocessing_job

# Step 2 — build and evaluate the classifier; promote to Champion if accuracy >= 80%
databricks bundle run model_build_evaluation_job

# Step 3 — deploy the Champion model to a Model Serving endpoint
databricks bundle run model_deployment_job

# Step 4 — run batch inference over all tickets
databricks bundle run batch_inference_job
```

---

## Configuration

All configuration is exposed as bundle variables with sensible defaults. No edits to source files are needed for most workspaces.

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

Or add persistent overrides to `databricks.yml` under the target's `variables:` block.

### Production target

```bash
databricks bundle deploy --target prod
databricks bundle run --target prod data_preprocessing_job
# ... etc.
```

The `prod` target uses `llmops_quickstart_prod` as the schema name.

---

## Project Structure

```
notebooks/
  1_data_preprocessing/
    data_ingestion.py         # Creates support_tickets Delta table (30 labelled rows)
  2_model_build_and_deploy/
    quickstart_agent.py       # MLflow ChatAgent definition
    model_config.yml          # Default agent config (llm_endpoint)
    model_build.py            # Logs agent to MLflow
    model_evaluation.py       # Evaluates agent; promotes to Champion if accuracy >= threshold
    model_deployment.py       # Deploys Champion to Mosaic AI Model Serving
  3_inference/
    batch_inference.py        # Batch predictions written to inference_results table
    realtime_inference.py     # Live queries via OpenAI-compatible API
resources/
  model_artifacts.yml         # UC schema + MLflow experiment resources
  1_data_preprocessing_job.yml
  2_1_model_build_evaluation_job.yml
  2_2_model_deployment_job.yml
  3_batch_inference_job.yml
databricks.yml                # Bundle entry point — targets, variables
```

---

## How It Works

1. **Data Ingestion** — 30 hand-labelled support tickets (6 per category) are written to a Delta table in Unity Catalog.
2. **Model Build** — `quickstart_agent.py` is logged as an MLflow `ChatAgent` model. The configured LLM endpoint is baked into the model artifact via `mlflow.models.ModelConfig`.
3. **Evaluation** — The logged agent runs predictions on all 30 tickets. If accuracy meets the threshold (default 80%), the model is registered in Unity Catalog and aliased as **Champion**.
4. **Deployment** — The Champion model version is deployed to a Mosaic AI Model Serving endpoint via `databricks.agents.deploy()`.
5. **Inference** — Batch inference loads the Champion model directly; real-time inference queries the serving endpoint via the OpenAI-compatible API.
