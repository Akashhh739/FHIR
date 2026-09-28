"""
Phase 5 — Local analytics with DuckDB over the exported Parquet files.

Prerequisites:
    pip install duckdb
    Run scripts/01_setup_synthea.sh to download the Parquet files first.

Usage:
    python scripts/02_duckdb_analytics.py
"""

import duckdb

GOLD = "gold_patient_features_parquet/*.parquet"

result = duckdb.sql(f"""
    SELECT
        readmitted_30d,
        ROUND(AVG(age), 1)              AS avg_age,
        ROUND(AVG(total_encounters), 1) AS avg_encounters,
        COUNT(*)                        AS patient_count
    FROM '{GOLD}'
    GROUP BY readmitted_30d
    ORDER BY readmitted_30d
""")

print(result)
# Expected output:
# readmitted_30d  avg_age  avg_encounters  patient_count
#              0     43.2           689.4           2746
#              1     68.1          1877.3            709
#
# Readmitted patients average 25 years older and 2.7x more encounters.
