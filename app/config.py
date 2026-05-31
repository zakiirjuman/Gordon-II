from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
CORPUS_DIR = BASE_DIR / "corpus"
DATA_DIR = BASE_DIR.parent / "data" / "officers"
INTERACTIONS_DIR = BASE_DIR.parent / "data" / "interactions"

APP_NAME = "Gordon II"
APP_TAGLINE = "Lawful patrol intelligence — not Batman."
CORPUS_VERSION = "gordon-ii-0.4"

GIS_BASE = "https://gis.toronto.ca/arcgis/rest/services/cot_geospatial2/FeatureServer"
CITY_WARDS_LAYER = 0
ROAD_RESTRICTIONS_LAYER = 77
CONSTRUCTION_HUBS_LAYER = 71

FIRE_STATIONS_GEOJSON = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
    "a6ce5495-8e2b-421a-ab11-964569416f31/resource/"
    "4a9bb96b-da5e-4c67-aaf4-3f8f4f311430/download/fire-station-locations-4326.geojson"
)
SCHOOLS_GEOJSON = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
    "1a714b5c-64c0-4cdf-9739-0086f80fb3ee/resource/"
    "f1160f3f-a651-40ed-914e-07b670ac5aec/download/"
    "school-locations-all-types-data-4326.geojson"
)

KSI_COLLISIONS_CSV = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
    "73a8e475-9683-42e1-ac06-b8690dcba062/resource/"
    "b95f5270-4eb0-40c2-917d-37fb494328a1/download/"
    "motor-vehicle-collisions-with-ksi-data-4326.csv"
)

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "nemotron3:33b"
OLLAMA_EMBED_MODEL = "nomic-embed-text"
EMBED_INDEX_PATH = BASE_DIR.parent / "data" / "embeddings" / "law_cards.json"
RAG_MODE = "auto"  # auto | embeddings | keyword

CACHE_TTL_SECONDS = 300

DEFAULT_POINT_RADIUS_M = 500
MOCK_BACKUP_ETA_MINUTES = 8

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_TIMEOUT_S = 4.0
GEOCODE_CACHE_SIZE = 128

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
