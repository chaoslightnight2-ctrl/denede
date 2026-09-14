import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

# Antivirüs/proxy TLS kesmesi arkasında HTTPS çalışsın diye OS sertifika deposuna güven.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
STATE_FILE = ROOT / "state.json"

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
