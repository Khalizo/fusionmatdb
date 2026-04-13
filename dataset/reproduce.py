"""
Reproduce the FusionMatDB dataset from scratch.

This script downloads all 65 ORNL semiannual progress reports, extracts
structured data using Gemini 3 Flash vision on Vertex AI, ingests the
SDC-IC ITER Material Library, and exports the final dataset to Parquet.

Requirements:
    pip install fusionmatdb
    export GOOGLE_CLOUD_API_KEY="your-vertex-ai-express-key"

Estimated cost: ~$40 (Gemini 3 Flash token pricing)
Estimated time: ~2 hours (downloads + extraction)
"""
import subprocess
import sys

def run(cmd):
    print(f"\n$ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"ERROR: command failed with exit code {result.returncode}")
        sys.exit(1)

# 1. Download all accessible ORNL reports (65 of 77 volumes, 1990–2024)
run("fusionmatdb build --pdf-dir data/ornl_pdfs --db fusionmatdb.sqlite --max-reports 80")

# 2. Ingest SDC-IC ITER Material Library (EUPL license, human-curated)
# Clone the repo first: git clone https://github.com/Structural-Mechanics/SDC-IC-Material-Library /tmp/sdc_ic
run("fusionmatdb ingest-sdc-ic --repo-path /tmp/sdc_ic --db fusionmatdb.sqlite")

# 3. Show database statistics
run("fusionmatdb stats --db fusionmatdb.sqlite")

# 4. Export to Parquet and world model formats
run("fusionmatdb export --format parquet --output data/fusionmatdb_export --db fusionmatdb.sqlite")
run("fusionmatdb export --format world_model --output data/fusionmatdb_export --db fusionmatdb.sqlite")

print("\n✅ Dataset reproduced. Upload to HuggingFace:")
print("   huggingface-cli upload Khalizo/fusionmatdb data/ --repo-type dataset")
