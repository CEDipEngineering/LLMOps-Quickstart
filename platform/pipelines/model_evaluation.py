# Databricks notebook source
# Uses Databricks Serverless Environment v5 (configured in job resource YAML).
# databricks-openai and pyyaml are added via the job's environment spec.

# COMMAND ----------
# MAGIC %md
# MAGIC # Model Evaluation
# MAGIC
# MAGIC Evaluates the logged agent against the labelled evaluation dataset.
# MAGIC Metrics are logged to the same MLflow run.  If accuracy meets the threshold
# MAGIC defined in `developer/agent_config.yml`, the model is registered to Unity
# MAGIC Catalog and aliased as **Champion**.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "main")
dbutils.widgets.text("schema_name", "llmops_quickstart")
dbutils.widgets.text("model_name", "support_ticket_classifier")
dbutils.widgets.text("logged_run_id", "")
dbutils.widgets.text("experiment_name", f"/Users/{dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()}/llmops_quickstart")
dbutils.widgets.text("bundle_root", "")

catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")
model_name = dbutils.widgets.get("model_name")
logged_run_id = dbutils.widgets.get("logged_run_id")
experiment_name = dbutils.widgets.get("experiment_name")
bundle_root = dbutils.widgets.get("bundle_root")

registered_model_name = f"{catalog_name}.{schema_name}.{model_name}"
model_uri = f"runs:/{logged_run_id}/agent"

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

eval_cfg = agent_config["eval"]
eval_table = eval_cfg["table_name"]
input_column = eval_cfg["input_column"]
expected_column = eval_cfg["expected_output_column"]
accuracy_threshold = float(eval_cfg["accuracy_threshold"])

print(f"Eval table:         {catalog_name}.{schema_name}.{eval_table}")
print(f"Input column:       {input_column}")
print(f"Expected column:    {expected_column}")
print(f"Accuracy threshold: {accuracy_threshold:.0%}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Load agent and run predictions

# COMMAND ----------

import mlflow

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(experiment_name)

agent = mlflow.pyfunc.load_model(model_uri)

df = spark.read.table(f"{catalog_name}.{schema_name}.{eval_table}").toPandas()

results = []
for _, row in df.iterrows():
    prediction = agent.predict({"messages": [{"role": "user", "content": str(row[input_column])}]})
    messages = prediction.get("messages", [])
    predicted = messages[-1].get("content", "").strip().lower() if messages else ""
    expected = str(row[expected_column]).strip().lower()
    results.append({
        "input": row[input_column],
        "expected": expected,
        "predicted": predicted,
        "correct": predicted == expected,
    })

import pandas as pd
results_df = pd.DataFrame(results)
display(results_df)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Log evaluation metrics

# COMMAND ----------

accuracy = results_df["correct"].mean()
n_total = len(results_df)
n_correct = results_df["correct"].sum()

print(f"Accuracy: {n_correct}/{n_total} = {accuracy:.1%}")

with mlflow.start_run(run_id=logged_run_id):
    mlflow.log_metrics({
        "eval/accuracy": accuracy,
        "eval/n_total": n_total,
        "eval/n_correct": int(n_correct),
    })

# COMMAND ----------
# MAGIC %md
# MAGIC ## Register model as Champion if threshold is met

# COMMAND ----------

from mlflow import MlflowClient

if accuracy >= accuracy_threshold:
    print(f"Accuracy {accuracy:.1%} >= threshold {accuracy_threshold:.0%} — registering model.")
    client = MlflowClient()
    registered = mlflow.register_model(model_uri, name=registered_model_name)
    client.set_registered_model_alias(registered_model_name, "Champion", registered.version)
    print(f"Registered {registered_model_name} v{registered.version} as Champion.")
    dbutils.jobs.taskValues.set(key="model_version", value=registered.version)
else:
    raise Exception(
        f"Accuracy {accuracy:.1%} is below threshold {accuracy_threshold:.0%}. "
        "Model not registered. Improve the agent and re-run."
    )
