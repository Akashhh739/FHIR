# Clinical Lakehouse & Patient AI Copilot

End-to-end data engineering and ML pipeline on 3,455 synthetic FHIR R4 patients —
Bronze → Silver → Gold → MLflow model registry → LLM text-to-SQL agent.

## Architecture

```
Synthea (Java/Gradle)
  └── ~13 GB FHIR R4 JSON bundles
        └── Unity Catalog Volume (synthea_raw/fhir)
              └── Auto Loader (cloudFiles) ──► bronze_fhir_bundles  (raw JSON, Delta)
                    └── PySpark FHIR parsing
                          ├── silver_patients     (demographics)
                          ├── silver_encounters   (visit history + encounter class)
                          ├── silver_conditions   (diagnoses, SNOMED CT)
                          └── silver_observations (vitals/labs)
                                └── Window functions + GroupBy
                                      └── gold_patient_features  (1 row/patient)
                                            ├── MLflow ──► readmission_risk_model (UC Registry)
                                            └── Parquet export
                                                  ├── DuckDB analytics
                                                  ├── Power BI (DirectQuery via SQL Warehouse)
                                                  └── LLM text-to-SQL agent
```

## Results

| Metric | Value |
|---|---|
| Patients | 3,455 synthetic (Synthea FHIR R4) |
| Raw data | ~13 GB JSON |
| Silver tables | 4 (patients, encounters, conditions, observations) |
| Readmission label | 20.5% positive (CMS-style: inpatient + emergency only) |
| Model (Random Forest) | F1: **0.599** · Avg Precision: **0.669** · Recall (readmitted): **0.70** |
| Key insight | Readmitted patients average **25 years older** and **2.7× more encounters** |

## Tech Stack

- **Databricks** — Unity Catalog, Auto Loader, serverless PySpark, Delta Lake, MLflow, SQL Warehouse, Dashboards
- **scikit-learn** — Random Forest classifier, class imbalance handling
- **DuckDB** — local analytics over Parquet
- **Power BI** — live DirectQuery dashboards via Databricks SQL Warehouse connector
- **OpenAI function calling** — LLM text-to-SQL agent grounded in real query results

## Engineering decisions worth noting

### FHIR reference format (`urn:uuid`)
Synthea uses `urn:uuid:<patient-id>` for subject references, not the `Patient/<id>` format in real EHRs.
Using the wrong regex silently produces empty `patient_id` values — breaking every downstream join with no obvious error.

### Schema inference on 13 GB
Full schema inference on all files silently ran out of memory on free-tier serverless compute.
Fixed by inferring from 20 sample files; the schema is stable across Synthea output, so this is safe here.

### Readmission label bug (98.7% → 20.5%)
The first label definition flagged 98.7% of patients as "readmitted" — obviously wrong.
Root cause: Synthea simulates 70+ years of medical history; a typical patient has 700+ encounters.
Any two consecutive visits land within 30 days by sheer density.
Fix: filter to `encounter_class IN ('IMP', 'EMER')` before computing the lead window — matching the CMS
30-day hospital readmission definition. Result: 20.5% positive, matching the real-world 15–20% rate.

### `try_cast` for polymorphic observation values
`Observation.valueQuantity.value` is only populated for numeric vitals.
Coded observations (e.g. "Tobacco smoking status") have no numeric value.
`try_cast(... AS DOUBLE)` returns `null` instead of failing; non-numeric rows are still stored.

### Class imbalance
80/20 split (non-readmitted / readmitted). Used `class_weight="balanced"` in the Random Forest
rather than resampling — penalizes minority-class misclassification without changing the training distribution.

## Power BI — Live Connection

Connect Power BI Desktop to the live Delta tables via the Databricks SQL Warehouse connector:

1. **Get Data → Databricks** — enter your workspace hostname and SQL Warehouse HTTP path
2. Use **DirectQuery** mode (not Import) to keep data live against the Delta tables
3. Key DAX measures:

```dax
Readmission Rate =
    DIVIDE(
        CALCULATE(COUNTROWS(gold_patient_features), gold_patient_features[readmitted_30d] = 1),
        COUNTROWS(gold_patient_features)
    )
```

Suggested pages: Population Overview · Readmission Risk · Condition Burden · Encounter Trends

The SQL Warehouse auto-suspends when idle — no compute cost while Power BI is closed.

## Repository structure

```
notebooks/
  clinical_lakehouse_pipeline.ipynb   Main Databricks notebook — all phases with explanations
scripts/
  01_setup_synthea.sh                 Clone Synthea, generate patients, upload to Databricks
  02_duckdb_analytics.py              Local analytics over exported Parquet
  03_text_to_sql_agent.py             LLM text-to-SQL agent (OpenAI function calling)
project_summary.md                    Full phase-by-phase writeup
```

## Running locally (DuckDB scripts only)

The Databricks notebook requires a Databricks workspace. The local scripts run after
downloading the exported Parquet files:

```bash
# 1. Clone, generate, upload (requires Databricks CLI configured)
bash scripts/01_setup_synthea.sh


# 2. Run the notebook in Databricks
# (open notebooks/clinical_lakehouse_pipeline.ipynb, attach to a cluster)

# 3. Download Parquet exports (included in 01_setup_synthea.sh)
# Then run local scripts:
pip install duckdb openai
python scripts/02_duckdb_analytics.py

export OPENAI_API_KEY=sk-...
python scripts/03_text_to_sql_agent.py
```

## Data

Patient data generated with **[Synthea](https://github.com/synthetichealth/synthea)** — an open-source synthetic patient generator by The MITRE Corporation.
All patients are entirely fictional. No real patient data was used.

> Walonoski J, et al. "Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record." *JAMIA* 2018; 25(3):230–238. [doi:10.1093/jamia/ocx079](https://doi.org/10.1093/jamia/ocx079)
