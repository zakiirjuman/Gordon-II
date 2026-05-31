from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
CORPUS_DIR = BASE_DIR / "corpus"
DATA_DIR = BASE_DIR.parent / "data" / "officers"
INTERACTIONS_DIR = BASE_DIR.parent / "data" / "interactions"

APP_NAME = "Gordon II"
APP_TAGLINE = "Lawful patrol intelligence — not Batman."
CORPUS_VERSION = "gordon-ii-0.2"

GIS_BASE = "https://gis.toronto.ca/arcgis/rest/services/cot_geospatial2/FeatureServer"
ROAD_RESTRICTIONS_LAYER = 77
CONSTRUCTION_HUBS_LAYER = 71

KSI_COLLISIONS_CSV = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
    "73a8e475-9683-42e1-ac06-b8690dcba062/resource/"
    "b95f5270-4eb0-40c2-917d-37fb494328a1/download/"
    "motor-vehicle-collisions-with-ksi-data-4326.csv"
)

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "nemotron3:33b"

CACHE_TTL_SECONDS = 300

DEFAULT_POINT_RADIUS_M = 500
MOCK_BACKUP_ETA_MINUTES = 8

ASR_BACKEND = "auto"
NIM_ASR_URL = "http://127.0.0.1:8010"
NIM_ASR_MODEL = "parakeet-tdt-0.6b-v3"
NEMO_ASR_MODEL = "nvidia/parakeet-tdt-0.6b-v3"

WHISPER_MODEL = "distil-large-v3"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float16"
WHISPER_CPU_COMPUTE_TYPE = "int8"

SPEAKER_MATCH_THRESHOLD = 0.72
SPEAKER_CLUSTER_THRESHOLD = 0.68
VOICE_WAKE_TERMS = ("gordon", "hey gordon", "ok gordon")
DEFAULT_OFFICER_ID = "device-officer"
