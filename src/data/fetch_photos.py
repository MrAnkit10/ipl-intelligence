"""Fetch player and venue photos from Wikimedia (blueprint section 14/43).

Players are matched via Wikidata property P2697 ("Cricinfo player ID"),
using the key_cricinfo id already in players.parquet (from Cricsheet's
people register) as an exact join key — not name search. This matters: an
earlier name-search-based version of this script silently attached Steve
Smith's photo to Josh Hazlewood and the IPL tournament logo to Marcus
Stoinis, because initials-only names like "JR Hazlewood" search ambiguously
and "cricket" appears on nearly every cricket-related page, so a weak
keyword check waved both through. An exact ID match can't make that
mistake — a player with no P2697 claim (or none tagged with a photo)
simply gets no photo, never a wrong one.

Venues have no equivalent ID in our data, so they're matched by name
search (find_venue_photo) — lower collision risk than player names since
venue names are far more distinctive, but still verified by requiring the
venue's own distinguishing word to appear in the matched Wikipedia title.

Results are cached to data/processed/player_photos.csv and
venue_photos.csv so this only needs to run once; re-run any time to
refresh.

Usage:
    python -m src.data.fetch_photos
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"

USER_AGENT = "IPL-Intelligence-Portfolio-Project/1.0 (https://github.com/MrAnkit10/ipl-intelligence; ankitkanani17@gmail.com)"
SPARQL_URL = "https://query.wikidata.org/sparql"
SEARCH_URL = "https://en.wikipedia.org/w/api.php"
SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
BATCH_SIZE = 75
REQUEST_DELAY = 0.3
TIMEOUT = 30

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def _sparql(query: str) -> list[dict]:
    try:
        resp = session.get(SPARQL_URL, params={"query": query, "format": "json"}, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("results", {}).get("bindings", [])
    except (requests.RequestException, ValueError):
        return []


def _commons_filepath_to_thumbnail(file_url: str, width: int = 330) -> str:
    """Wikidata P18 gives a Special:FilePath URL (full resolution); turn it
    into a sized thumbnail URL the way Wikipedia's own summary API does."""
    filename = file_url.rsplit("/", 1)[-1]
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width={width}"


def fetch_player_photos_batch(cricinfo_ids: list[str]) -> dict[str, str]:
    """cricinfo_id -> photo_url, for whichever ids resolve to a Wikidata
    item with a P18 (image) claim."""
    values = " ".join(f'"{cid}"' for cid in cricinfo_ids)
    query = f"""
    SELECT ?cricinfoId ?image WHERE {{
      VALUES ?cricinfoId {{ {values} }}
      ?item wdt:P2697 ?cricinfoId.
      ?item wdt:P18 ?image.
    }}
    """
    results = {}
    for row in _sparql(query):
        cid = row["cricinfoId"]["value"]
        image_url = row["image"]["value"]
        results[cid] = _commons_filepath_to_thumbnail(image_url)
    return results


def fetch_player_photos(players: pd.DataFrame) -> pd.DataFrame:
    with_cricinfo = players.dropna(subset=["key_cricinfo"]).copy()
    with_cricinfo["key_cricinfo"] = with_cricinfo["key_cricinfo"].astype(str)
    id_to_player = with_cricinfo.set_index("key_cricinfo")["player_id"].to_dict()

    all_ids = list(id_to_player.keys())
    photo_by_cricinfo_id = {}
    for i in range(0, len(all_ids), BATCH_SIZE):
        batch = all_ids[i : i + BATCH_SIZE]
        photo_by_cricinfo_id.update(fetch_player_photos_batch(batch))
        print(f"  players: {min(i + BATCH_SIZE, len(all_ids))}/{len(all_ids)} ({len(photo_by_cricinfo_id)} photos so far)")
        time.sleep(REQUEST_DELAY)

    rows = [
        {"player_id": pid, "photo_url": photo_by_cricinfo_id.get(cid)}
        for cid, pid in id_to_player.items()
    ]
    # Players with no key_cricinfo at all still get a row (no photo) so
    # callers can rely on every player_id being present.
    no_cricinfo_ids = set(players["player_id"]) - set(id_to_player.values())
    rows += [{"player_id": pid, "photo_url": None} for pid in no_cricinfo_ids]
    return pd.DataFrame(rows)


def _search_top_title(query: str) -> str | None:
    try:
        resp = session.get(
            SEARCH_URL,
            params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 1},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("query", {}).get("search", [])
        return results[0]["title"] if results else None
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def _fetch_summary(title: str) -> dict | None:
    try:
        resp = session.get(SUMMARY_URL.format(title=title.replace(" ", "_")), timeout=TIMEOUT)
        if resp.status_code != 200:
            return None
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


# Generic venue-naming vocabulary, excluded when picking the "distinguishing"
# word to verify a search match against — otherwise e.g. "Dr DY Patil Sports
# Academy" pick "Academy" (7 letters) over the actual identifying name
# "Patil" (5 letters), and a real match like "DY Patil Stadium" fails the
# check just because it doesn't happen to repeat the word "Academy".
GENERIC_VENUE_WORDS = {
    "stadium", "cricket", "ground", "association", "academy", "international",
    "sports", "complex", "club", "oval", "park", "arena", "the", "dr", "dr.",
    "is", "national", "state", "district", "college", "university",
}


def find_venue_photo(venue: str) -> tuple[str | None, str | None]:
    primary_name = venue.split(",")[0].strip()
    distinguishing_words = [w.lower() for w in primary_name.split() if w.lower() not in GENERIC_VENUE_WORDS]
    if not distinguishing_words:
        distinguishing_words = [w.lower() for w in primary_name.split()]

    title = _search_top_title(f"{primary_name} cricket ground")
    if not title:
        return None, None
    time.sleep(REQUEST_DELAY)

    summary = _fetch_summary(title)
    if not summary or summary.get("type") == "disambiguation":
        return None, None

    description = summary.get("description", "").lower()
    title_lower = title.lower()
    is_venue_page = "cricket" in description and ("stadium" in description or "ground" in description)
    name_matches = any(word in title_lower for word in distinguishing_words)
    if not (is_venue_page and name_matches):
        return None, None

    thumbnail = summary.get("thumbnail", {}).get("source")
    return thumbnail, title


def fetch_venue_photos(venues: list[str]) -> pd.DataFrame:
    rows = []
    for i, venue in enumerate(venues, start=1):
        photo_url, wiki_title = find_venue_photo(venue)
        rows.append({"venue": venue, "photo_url": photo_url, "wikipedia_title": wiki_title})
        time.sleep(REQUEST_DELAY)
        print(f"  venues: {i}/{len(venues)} -> {'found' if photo_url else 'not found'}: {venue}")
    return pd.DataFrame(rows)


def main() -> None:
    players = pd.read_parquet(PROCESSED_DIR / "players.parquet")
    venue_stats = pd.read_csv(PROCESSED_DIR / "venue_stats.csv")

    print(f"Fetching photos for {len(players)} players (via Cricinfo ID)...")
    player_photos = fetch_player_photos(players)
    player_photos.to_csv(PROCESSED_DIR / "player_photos.csv", index=False)
    found = player_photos["photo_url"].notna().sum()
    print(f"player_photos.csv: {found}/{len(player_photos)} matched -> {PROCESSED_DIR / 'player_photos.csv'}")

    print(f"\nFetching photos for {len(venue_stats)} venues (via name search)...")
    venue_photos = fetch_venue_photos(sorted(venue_stats["venue"].unique()))
    venue_photos.to_csv(PROCESSED_DIR / "venue_photos.csv", index=False)
    found = venue_photos["photo_url"].notna().sum()
    print(f"venue_photos.csv: {found}/{len(venue_photos)} matched -> {PROCESSED_DIR / 'venue_photos.csv'}")


if __name__ == "__main__":
    main()
