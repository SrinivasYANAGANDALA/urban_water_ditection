from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    SAMPLE_DATA_FILE = BASE_DIR / "sample_data" / "water_data.csv"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
