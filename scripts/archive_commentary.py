"""
Appends today's commentary to the notes archive (data/notes_archive.json).
Run after ai_commentary.py each day.
"""
import json, os
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load(path):
    try:
        with open(os.path.join(BASE, path)) as f:
            return json.load(f)
    except:
        return None

def save(path, data):
    with open(os.path.join(BASE, path), "w") as f:
        json.dump(data, f, indent=2)

today = load("data/commentary.json")
if not today:
    print("No commentary.json found, skipping archive")
    exit(0)

archive = load("data/notes_archive.json") or []

# Don't duplicate — check if today's date already in archive
if archive and archive[0].get("date") == today.get("date"):
    print(f"Already archived for {today.get('date')}, skipping")
    exit(0)

# Prepend today to archive (newest first)
archive.insert(0, today)
archive = archive[:90]  # keep 90 days

save("data/notes_archive.json", archive)
print(f"✓ Archived note for {today.get('date')} — archive has {len(archive)} entries")
