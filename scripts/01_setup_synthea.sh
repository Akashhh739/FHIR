#!/usr/bin/env bash
# Phase 1 — Generate synthetic patients with Synthea and upload to Databricks
# Run from the project root: bash scripts/01_setup_synthea.sh

set -e

# ── 1. Clone and build Synthea ────────────────────────────────────────────────
git clone https://github.com/synthetichealth/synthea.git
cd synthea

./gradlew build check test

# Generate ~3,455 patients (adjust -p for a different count)
./run_synthea -p 3000

# Output lands in synthea/output/fhir/ — ~13 GB of FHIR R4 JSON bundles

# ── 2. Install and configure the Databricks CLI ───────────────────────────────
brew tap databricks/tap
brew install databricks

# Paste your workspace URL and personal access token when prompted
databricks configure --token

# ── 3. Upload FHIR bundles to a Unity Catalog Volume ─────────────────────────
databricks fs cp -r output/fhir \
    dbfs:/Volumes/main/default/synthea_raw/fhir \
    --overwrite

# ── 4. Download exported Parquet files after running the Databricks notebook ──
# Run this after clinical_lakehouse_pipeline.ipynb has completed the export step.
databricks fs cp -r \
    dbfs:/Volumes/main/default/synthea_raw/exports/gold_patient_features_parquet \
    ./gold_patient_features_parquet

databricks fs cp -r \
    dbfs:/Volumes/main/default/synthea_raw/exports/silver_conditions_parquet \
    ./silver_conditions_parquet

databricks fs cp -r \
    dbfs:/Volumes/main/default/synthea_raw/exports/silver_encounters_parquet \
    ./silver_encounters_parquet
