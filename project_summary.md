# Project Summary: Clinical Lakehouse & Patient AI Copilot

## Data Source
- **Synthea** (open-source synthetic patient generator) — 3,455 synthetic patients, realistic FHIR R4 medical histories, generated locally via Java/Gradle

## Phase 1: Bronze Layer (Databricks)
- Uploaded ~13GB of Synthea JSON bundles to a **Unity Catalog Volume** (`main.default.synthea_raw`)
- Used **Auto Loader** (`cloudFiles`) to ingest raw files into `bronze_fhir_bundles` — untouched, raw JSON, one row per patient bundle

## Phase 2: Silver Layer (PySpark)
Parsed and flattened the deeply nested, polymorphic FHIR JSON into 4 clean, queryable Delta tables:
- **`silver_patients`** — demographics (id, gender, birth date, name, city/state)
- **`silver_encounters`** — visit history (dates, reason, encounter class: ambulatory/emergency/inpatient)
- **`silver_conditions`** — diagnoses (name, code, clinical status, onset)
- **`silver_observations`** — vitals/labs (BMI, heart rate, etc.)

Solved real FHIR engineering problems along the way: schema inference failures on polymorphic fields, `urn:uuid:` reference resolution, and joining on a common `patient_id` key. Formalized these relationships with declared **primary/foreign key constraints** in Unity Catalog.

## Phase 3: Gold Layer
- **`gold_patient_features`** — one row per patient, built with window functions and GroupBys: age, total encounters, active chronic condition count, latest vitals
- Derived a **30-day readmission label** from Encounters (inpatient/emergency visits within 30 days of each other) — caught and fixed an initial broken version that had a 98.7% positive rate, replaced with a realistic ~20.5% rate

## Phase 4: ML with MLflow
- Trained a **Random Forest classifier** (scikit-learn) to predict 30-day readmission risk
- Handled class imbalance with `class_weight="balanced"`
- Logged params/metrics (**F1: 0.599, Average Precision: 0.669**) and registered the model in the **Databricks Model Registry** (Unity Catalog) as `main.default.readmission_risk_model`

## Analytics Layer
- Exported Gold/Silver tables to **Parquet**, queried locally with **DuckDB** — found a real insight: readmitted patients average 25 years older and 2.7x more encounters than non-readmitted patients
- Set up **Databricks Dashboards** (browser-native BI) and discussed **Power BI** as a live-connection alternative (via the SQL Warehouse connector)

## Phase 5: AI Layer
- Extracted real clinical notes (`DocumentReference` resources, base64-decoded) into `silver_clinical_notes` — available for future RAG work if wanted
- Landed on a **text-to-SQL agent** instead of embedding-based RAG (better fit for structured data): built a Python script (`ask.py`) where an LLM (via OpenAI function calling) writes its own SQL against the DuckDB/Parquet tables to answer free-form questions, grounded in real query results — not hallucinated

## Architecture
```
Synthea -> Volume -> Auto Loader -> Bronze (raw JSON)
                                    |
                    Silver (Patients/Encounters/Conditions/Observations)
                                    |
                    Gold (patient_features + readmission label)
                                    |
                    MLflow (Random Forest, registered model)
                                    |
                    Parquet export -> DuckDB -> LLM text-to-SQL agent
```

## What's left / optional
- Wrap `ask.py` in a **FastAPI** endpoint (the original plan's Phase 5 API layer)
- Live Power BI connection via SQL Warehouse
- Real RAG over `silver_clinical_notes` if you want a second AI pattern
- A proper README with this architecture diagram, the numbers above, and honest notes on the design decisions (FHIR polymorphism handling, the readmission label fix, the class imbalance trade-off)

That last README point is genuinely valuable — the "I found a bug in my own label and fixed it" story is a stronger interview answer than a project that "just worked."
