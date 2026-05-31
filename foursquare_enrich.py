#!/usr/bin/env python3
"""
Enrich experience files with Foursquare Places API data.
Adds/updates: foursquare_id, categoria_fsq, website, and missing Instagram.

Requires env var: FOURSQUARE_API_KEY

Usage:
  python foursquare_enrich.py              # update all files
  python foursquare_enrich.py --dry-run    # preview without writing
  python foursquare_enrich.py --force      # re-fetch even if already enriched
"""

import os
import re
import sys
import time
import json
import urllib.request
import urllib.parse
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv
FORCE = "--force" in sys.argv
CONTENT_DIR = Path(__file__).parent / "src/content/experiencias"
API_KEY = os.environ.get("FOURSQUARE_API_KEY", "")
BASE_URL = "https://places-api.foursquare.com/places"
DELAY = 0.5  # seconds between requests




# ── Foursquare API helpers ────────────────────────────────────────────────────

def fsq_request(path: str, params: dict) -> dict | None:
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Accept": "application/json",
            "X-Places-Api-Version": "2025-06-17",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode(errors="replace")
        except Exception:
            body = "<could not read body>"
        print(f"  ⚠  HTTP {exc.code} for {path}: {body[:200]}")
    except Exception as exc:
        print(f"  ⚠  Request error for {path}: {exc}")
    return None


def search_place(name: str, lat: float, lon: float) -> dict | None:
    """Search by name near coordinates. Uses only free Pro-tier fields."""
    data = fsq_request("/search", {
        "query": name,
        "ll": f"{lat},{lon}",
        "radius": 200,
        "limit": 1,
        "fields": "fsq_place_id,name,categories,location,distance,website,tel,social_media",
    })
    if data and data.get("results"):
        return data["results"][0]
    return None


# ── Frontmatter injection ─────────────────────────────────────────────────────

def _yaml_str(value: str) -> str:
    """Wrap a string in YAML double quotes, escaping inner quotes."""
    return '"' + value.replace('"', '\\"') + '"'


def inject_fsq_fields(fm: str, fields: dict) -> str:
    """
    Insert/replace Foursquare fields at the top level of the frontmatter.
    Instagram is only added when the file does not already have one.
    """
    lines = []

    for key in ("foursquare_id", "categoria_fsq", "website"):
        value = fields.get(key)
        if not value:
            continue
        fm = re.sub(rf"^{key}:.*\n", "", fm, flags=re.MULTILINE)
        lines.append(f"{key}: {_yaml_str(value)}")

    if fields.get("instagram") and not re.search(r"^instagram:", fm, re.MULTILINE):
        instagram = fields["instagram"].lstrip("@").strip()
        if instagram:
            lines.append(f"instagram: {_yaml_str(instagram)}")
            lines.append(f"instagramUrl: {_yaml_str(f'https://www.instagram.com/{instagram}/')}")

    if not lines:
        return fm

    insertion = "\n".join(lines) + "\n"

    # Insert before content-ish fields when possible, keeping metadata grouped.
    insert_match = re.search(r"^(description|images|source):", fm, re.MULTILINE)
    if insert_match:
        pos = insert_match.start()
        return fm[:pos] + insertion + fm[pos:]

    # Fallback: append before end
    return fm.rstrip("\n") + "\n" + insertion + "\n"


# ── File processing ───────────────────────────────────────────────────────────

def process_file(md_path: Path) -> bool:
    text = md_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)---\n(.*)", text, re.DOTALL)
    if not match:
        return False

    fm, body = match.group(1), match.group(2)

    # Skip if already enriched (unless --force)
    if not FORCE and "foursquare_id:" in fm:
        print(f"  already enriched — skipping (use --force to re-fetch)")
        return False

    # Extract title and first address with lat/lng
    title_m = re.search(r'^title:\s*"([^"]+)"', fm, re.MULTILINE)
    lat_m = re.search(r"lat: ([\d\.\-]+)", fm)
    lng_m = re.search(r"lng: ([\d\.\-]+)", fm)

    if not title_m:
        print(f"  skip: no title")
        return False
    if not lat_m or not lng_m:
        print(f"  skip: no lat/lng (run geocode_experiencias.py first)")
        return False

    title = title_m.group(1)
    lat = float(lat_m.group(1))
    lon = float(lng_m.group(1))

    # Step 1: search (all needed fields returned in one request)
    print(f"  searching: {title!r} near ({lat}, {lon})")
    result = search_place(title, lat, lon)
    time.sleep(DELAY)

    if not result:
        print(f"  ⚠  not found on Foursquare")
        return False

    fsq_id = result.get("fsq_place_id", "")
    found_name = result.get("name", "?")
    dist = result.get("distance", "?")
    print(f"  found: {found_name!r}  id={fsq_id}  dist={dist}m")

    # Extract free Pro-tier fields
    categories = result.get("categories", [])
    categoria = categories[0]["name"] if categories else ""

    website = result.get("website", "")
    tel = result.get("tel", "")

    social = result.get("social_media", {}) or {}
    instagram_fsq = social.get("instagram", "")

    print(f"  categoria: {categoria!r}")
    print(f"  website:   {website!r}")
    print(f"  tel:       {tel!r}")
    print(f"  instagram: {instagram_fsq!r}")

    fields = {
        "foursquare_id": fsq_id,
        "categoria_fsq": categoria,
        "website": website,
        "instagram": instagram_fsq,
    }

    new_fm = inject_fsq_fields(fm, fields)
    new_text = f"---\n{new_fm}---\n{body}"

    if DRY_RUN:
        print(f"  [DRY-RUN] would write {md_path.name}")
    else:
        md_path.write_text(new_text, encoding="utf-8")
        print(f"  ✓ wrote {md_path.name}")

    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not API_KEY:
        print("ERROR: FOURSQUARE_API_KEY environment variable is not set")
        sys.exit(1)

    md_files = sorted(CONTENT_DIR.rglob("*.md"))
    print(f"Found {len(md_files)} experience files")
    if DRY_RUN:
        print("DRY-RUN mode — no files will be written")
    if FORCE:
        print("FORCE mode — re-fetching all places")
    print()

    updated = 0
    not_found = []

    for md_path in md_files:
        print(f"\n{md_path.relative_to(CONTENT_DIR)}")
        if process_file(md_path):
            updated += 1
        else:
            title_m = re.search(r'^title:\s*"([^"]+)"', md_path.read_text(), re.MULTILINE)
            if title_m and "not found" in "":
                not_found.append(title_m.group(1))

    print(f"\n{'='*50}")
    print(f"✓ Done — {updated}/{len(md_files)} files updated")
    if not_found:
        print(f"⚠  Not found on Foursquare: {', '.join(not_found)}")


if __name__ == "__main__":
    main()
