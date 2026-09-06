"""Download raw Cricsheet IPL data and the player identity register.

Usage:
    python -m src.data.download_data
"""

import zipfile
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
CRICSHEET_DIR = RAW_DIR / "cricsheet"
PLAYER_META_DIR = RAW_DIR / "player_metadata"

IPL_JSON_URL = "https://cricsheet.org/downloads/ipl_json.zip"
PEOPLE_CSV_URL = "https://cricsheet.org/register/people.csv"


def download_file(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    dest.write_bytes(response.content)
    return dest


def download_cricsheet_ipl() -> Path:
    zip_path = CRICSHEET_DIR / "ipl_json.zip"
    download_file(IPL_JSON_URL, zip_path)
    extract_dir = CRICSHEET_DIR / "ipl_json"
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    return extract_dir


def download_people_register() -> Path:
    return download_file(PEOPLE_CSV_URL, PLAYER_META_DIR / "people.csv")


if __name__ == "__main__":
    ipl_dir = download_cricsheet_ipl()
    people_csv = download_people_register()
    match_count = len(list(ipl_dir.glob("*.json")))
    print(f"Downloaded {match_count} IPL match files to {ipl_dir}")
    print(f"Downloaded player register to {people_csv}")
