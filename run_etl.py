#!/usr/bin/env python3
"""Run the A4/LEARN OMOP ETL pipeline.

Exits nonzero when any validation check fails, so wrapping scripts and CI
notice instead of loading an output that failed its own checks.
"""

import sys

from a4_omop_etl.pipeline import main

if __name__ == "__main__":
    results = main()
    sys.exit(0 if all(results['validation'].values()) else 1)
