# Databricks notebook source
# Uses Databricks Serverless Environment v5 (configured in job resource YAML).
# pyyaml is added via the job's environment spec.

# COMMAND ----------
# MAGIC %md
# MAGIC # Batch Inference
# MAGIC
# MAGIC Runs the Champion model over the input table defined in
# MAGIC `developer/agent_config.yml` and writes predictions to a results table.

# COMMAND ----------

dbutils.widgets.text("catalog_name", "main")
dbutils.widgets.text("schema_name", "llmops_quickstart")
dbutils.widgets.text("model_name", "support_ticket_classifier")
dbutils.widgets.text("bundle_root", "")

catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")
model_name = dbutils.widgets.get("model_name")
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

inf_cfg = agent_config["inference"]
input_table = inf_cfg["input_table"]
input_column = inf_cfg["input_column"]
output_table = inf_cfg["output_table"]

print(f"Input table:  {catalog_name}.{schema_name}.{input_table}")
print(f"Input column: {input_column}")
print(f"Output table: {catalog_name}.{schema_name}.{output_table}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Load Champion model and run predictions

# COMMAND ----------

import mlflow

mlflow.set_registry_uri("databricks-uc")

model_uri = f"models:/{registered_model_name}@Champion"
agent = mlflow.pyfunc.load_model(model_uri)

df = spark.read.table(f"{catalog_name}.{schema_name}.{input_table}").toPandas()


def extract_prediction(text: str) -> str:
    result = agent.predict({"messages": [{"role": "user", "content": str(text)}]})
    messages = result.get("messages", [])
    return messages[-1].get("content", "").strip() if messages else ""


df["prediction"] = df[input_column].apply(extract_prediction)

display(df)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Write predictions to Delta table

# COMMAND ----------

result_df = spark.createDataFrame(df)
result_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog_name}.{schema_name}.{output_table}")

print(f"Results written to {catalog_name}.{schema_name}.{output_table}")
print(f"Row count: {len(df)}")
