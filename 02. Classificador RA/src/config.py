import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o-mini"

SHOW_API_USAGE = os.getenv("SHOW_API_USAGE", "true").lower() == "true"
SHOW_API_USAGE_DETAILS = os.getenv("SHOW_API_USAGE_DETAILS", "false").lower() == "true"
API_USAGE_LOG_FILE = "output/openai_usage.json"

RECLAME_AQUI_URL = "https://www.reclameaqui.com.br/empresa/mercedes-benz-cars-e-vans"
MAX_PAGES = 20
REQUEST_DELAY = 2

SAMPLE_SIZE_FOR_DISCOVERY = 200
MIN_CATEGORIES = 6
MAX_CATEGORIES = 10

DATA_DIR = "data"
OUTPUT_DIR = "output"

COMPLAINTS_FILE = os.path.join(DATA_DIR, "complaints_raw.json")
PROPOSED_TAXONOMY_FILE = os.path.join(OUTPUT_DIR, "proposed_taxonomy.json")
CURATED_TAXONOMY_FILE = os.path.join(OUTPUT_DIR, "curated_taxonomy.json")
CLASSIFICATION_RESULTS_FILE = os.path.join(OUTPUT_DIR, "classification_results.json")
