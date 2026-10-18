import sys
from pathlib import Path
sys.path.insert(0, 'src')

from apophenic_memory.ingest.diary_parser import parse_diary
from apophenic_memory.timeline.builder import build_timeline, detect_gaps

print("--- FULL TIMELINE TEST ---")

entries = []
for f in ['test_data/entries_before.md', 'test_data/entries_after.md']:
    try:
        parsed = parse_diary(Path(f))
        print(f"{f}: {len(parsed)} entries")
        entries.extend(parsed)
    except Exception as e:
        print(f"Failed to parse {f}: {repr(e)}")

entries.sort(key=lambda x: x['date'])

print(f"Total entries merged: {len(entries)}")
if entries:
    print(f"Date range: {entries[0]['date']} to {entries[-1]['date']}")

gaps = detect_gaps(entries, min_days=14)
print(f"Gaps detected (>14 days): {len(gaps)}")
for g in gaps:
    print(f"  Gap from {g['start_date']} to {g['end_date']} ({g['gap_days']} days)")
