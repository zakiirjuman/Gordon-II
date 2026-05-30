from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

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
