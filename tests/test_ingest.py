from apophenic_memory.ingest.diary_parser import parse_diary


def test_parse_diary_from_text(tmp_path):
    source = tmp_path / "diary.md"
    source.write_text("""
2024-01-05: woke up late and felt restless
2024-01-08: went to the library and met Friend A
2024-01-20: rain on the window and a strange calm
""".strip(), encoding="utf-8")

    entries = parse_diary(source)

    assert entries == [
        {"date": "2024-01-05", "text": "woke up late and felt restless"},
        {"date": "2024-01-08", "text": "went to the library and met Friend A"},
        {"date": "2024-01-20", "text": "rain on the window and a strange calm"},
    ]
