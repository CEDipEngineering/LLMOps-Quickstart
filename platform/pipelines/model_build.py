# Databricks notebook source
# Uses Databricks Serverless Environment v5 (configured in job resource YAML).
# databricks-openai and pyyaml are added via the job's environment spec.

# COMMAND ----------
# MAGIC %md
# MAGIC # Model Build
# MAGIC
# MAGIC Logs the developer-defined `ChatAgent` to an MLflow experiment run and stores
# MAGIC the run ID for use by the evaluation task.  Agent path, pip requirements, and
# MAGIC model config are read from `developer/agent_config.yml`.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "main")
dbutils.widgets.text("schema_name", "llmops_quickstart")
dbutils.widgets.text("model_name", "support_ticket_classifier")
dbutils.widgets.text("experiment_name", f"/Users/{dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()}/llmops_quickstart")
dbutils.widgets.text("llm_endpoint", "databricks-claude-sonnet-4-6")
dbutils.widgets.text("bundle_root", "")

catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")
model_name = dbutils.widgets.get("model_name")
experiment_name = dbutils.widgets.get("experiment_name")
llm_endpoint = dbutils.widgets.get("llm_endpoint")
bundle_root = dbutils.widgets.get("bundle_root")

registered_model_name = f"{catalog_name}.{schema_name}.{model_name}"

# COMMAND ----------
# MAGIC %md
# MAGIC ## Load agent configuration

# COMMAND ----------

import yaml
import os

if bundle_root:
    config_path = os.path.join(bundle_root, "developer", "agent_config.yml")
else:
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "developer", "agent_config.yml")

with open(config_path) as f:
    agent_config = yaml.safe_load(f)

# Resolve the agent file path relative to the developer/ directory
if bundle_root:
    agent_file_path = os.path.join(bundle_root, "developer", agent_config["agent"]["file"])
else:
    agent_file_path = os.path.join(os.path.dirname(config_path), agent_config["agent"]["file"])

extra_pip = agent_config["agent"].get("extra_pip_requirements", [])

# The bundle variable llm_endpoint is authoritative (varies by target).
# Fall back to agent_config.yml for local development.
config_endpoint = agent_config.get("llm_endpoint", "")
model_config_values = {"llm_endpoint": llm_endpoint or config_endpoint}

print(f"Agent file:   {agent_file_path}")
print(f"Model config: {model_config_values}")
print(f"Extra pip:    {extra_pip}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Log agent to MLflow

# COMMAND ----------

import mlflow
import datetime
from mlflow.models.resources import DatabricksServingEndpoint

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(experiment_name)

resources = [DatabricksServingEndpoint(endpoint_name=model_config_values.get("llm_endpoint", llm_endpoint))]

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

with mlflow.start_run(run_name=f"build_{timestamp}") as run:
    logged_model_info = mlflow.pyfunc.log_model(
        artifact_path="agent",
        python_model=agent_file_path,
        model_config=model_config_values,
        resources=resources,
        pip_requirements=[
            "mlflow",
            "databricks-agents",
            "databricks-sdk",
            "typing_extensions",
        ] + extra_pip,
    )
    print(f"Logged model: {logged_model_info.model_uri}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Pass run ID to downstream evaluation task

# COMMAND ----------

dbutils.jobs.taskValues.set(key="logged_run_id", value=logged_model_info.run_id)
print(f"run_id: {logged_model_info.run_id}")
