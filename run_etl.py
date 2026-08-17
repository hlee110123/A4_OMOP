#!/usr/bin/env python3
"""Run the A4/LEARN OMOP ETL pipeline."""

from a4_omop_etl.pipeline import main

if __name__ == "__main__":
    results = main()
