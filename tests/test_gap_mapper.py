from apophenic_memory.gap_mapper.agent import detect_gap_descriptors


def test_detect_gap_descriptors_for_missing_periods():
    source = """
2024-01-01: felt heavy and distracted
2024-01-04: made it through class
2024-01-09: a quiet night at home
""".strip()

    gaps = detect_gap_descriptors(source, min_gap_days=4)

    assert len(gaps) == 1
    assert gaps[0].start_date == "2024-01-04"
    assert gaps[0].end_date == "2024-01-09"
    assert "gap" in gaps[0].reason.lower()
