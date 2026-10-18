import sys
from pathlib import Path

sys.path.insert(0, 'src')

from apophenic_memory.ingest.diary_parser import parse_diary
from apophenic_memory.ingest.photo_parser import parse_photos
from apophenic_memory.ingest.people_loader import load_people
from apophenic_memory.timeline.builder import build_timeline, detect_gaps

print("--- INGEST TEST ---")

diary = []
try:
    diary = parse_diary(Path('test_data/entries_before.md'))
    print(f"Diary entries found: {len(diary)}")
    if diary:
        print("First entry date:", diary[0].get('date'))
except Exception as e:
    print("Diary parse failed:", repr(e))

try:
    people = load_people(Path('test_data/people.json'))
    print(f"People loaded: {len(people)}")
    print("Names:", [p.get('name') for p in people])
except Exception as e:
    print("People load failed:", repr(e))

try:
    timeline = build_timeline(diary, [])
    print(f"Timeline built with {len(timeline)} entries")
    gaps = detect_gaps(timeline, min_days=14)
    print(f"Gaps detected: {len(gaps)}")
    if gaps:
        print("First gap:", gaps[0])
except Exception as e:
    print("Timeline build failed:", repr(e))
