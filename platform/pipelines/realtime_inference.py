# Databricks notebook source
# Uses Databricks Serverless Environment v5 (configured in job resource YAML).
# No %pip install needed — all required packages are pre-installed.

# COMMAND ----------
# MAGIC %md
# MAGIC # Realtime Inference
# MAGIC
# MAGIC Demonstrates querying the deployed Model Serving endpoint directly via the
# MAGIC OpenAI-compatible REST API using the Databricks SDK.  Sample inputs are read
# MAGIC from the evaluation dataset defined in `developer/agent_config.yml`.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "main")
dbutils.widgets.text("schema_name", "llmops_quickstart")
dbutils.widgets.text("model_name", "support_ticket_classifier")
dbutils.widgets.text("bundle_root", "")

catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")
model_name = dbutils.widgets.get("model_name")
bundle_root = dbutils.widgets.get("bundle_root")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Load agent configuration and discover endpoint

# COMMAND ----------

import yaml
import os

if bundle_root:
    config_path = os.path.join(bundle_root, "developer", "agent_config.yml")
else:
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "developer", "agent_config.yml")

with open(config_path) as f:
    agent_config = yaml.safe_load(f)

eval_cfg = agent_config["eval"]
eval_table = eval_cfg["table_name"]
input_column = eval_cfg["input_column"]

from databricks.agents import get_deployments
import mlflow
from mlflow import MlflowClient

mlflow.set_registry_uri("databricks-uc")
registered_model_name = f"{catalog_name}.{schema_name}.{model_name}"

deployments = get_deployments(model_name=registered_model_name)
assert deployments, f"No deployments found for {registered_model_name}. Run model_deployment first."

endpoint_name = deployments[0].endpoint_name
print(f"Using endpoint: {endpoint_name}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Send sample inputs to the endpoint

# COMMAND ----------

from databricks.sdk import WorkspaceClient

client = WorkspaceClient()
openai_client = client.serving_endpoints.get_open_ai_client()

# Read sample inputs from the evaluation dataset
sample_df = spark.read.table(f"{catalog_name}.{schema_name}.{eval_table}").limit(5).toPandas()
sample_inputs = sample_df[input_column].tolist()

for text in sample_inputs:
    response = openai_client.chat.completions.create(
        model=endpoint_name,
        messages=[{"role": "user", "content": text}],
    )
    result = response.choices[0].message.content.strip()
    print(f"[{result:25s}] {text}")
