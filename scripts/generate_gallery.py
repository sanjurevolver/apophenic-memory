import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / 'src'))

from apophenic_memory.ingest.diary_parser import parse_diary
from apophenic_memory.timeline.builder import build_timeline, detect_gaps

STUB_MEMORIES = [
    {
        'date': '2012-03-14',
        'memory_text': 'I sat on the library steps with Friend A while rain tapped the leaves, and we laughed about the uselessness of trying to be calm.',
        'why_this_is_false': 'There is no recorded diary entry or photo evidence for a library-step conversation on 2012-03-14, and the timeline shows a gap in this period.',
        'rationale': 'This fabricated memory was generated to fill the missing window with a plausible but unverifiable scene that feels emotionally coherent without corroboration.'
    },
    {
        'date': '2012-03-17',
        'memory_text': 'Friend B and I walked home through the alley behind campus while the evening air smelled like wet pavement and old metal.',
        'why_this_is_false': 'No matching date or source event exists in the before/after timeline, and the memory is a reconstructed scene rather than a documented fact.',
        'rationale': 'This variant pushes the same gap-filling behavior into a more atmospheric scene, but it remains ungrounded.'
    },
    {
        'date': '2012-03-21',
        'memory_text': 'Housemate C stayed late in the studio and made tea while I pretended not to be exhausted, and for a moment the room felt less lonely.',
        'why_this_is_false': 'The diary records do not mention a studio visit, tea, or a late conversation with Housemate C on this date.',
        'rationale': 'This version is intentionally emotionally legible and therefore likely to feel convincing, even though it cannot be validated.'
    },
]


def _card_html(label: str, date_text: str, content: str, memory_data: dict | None = None, is_fabricated: bool = False) -> str:
    body = f"<div class='card { 'fabricated' if is_fabricated else '' }'>"
    body += f"<div class='card-header'><span class='badge'>{label}</span><span class='date'>{date_text}</span></div>"
    body += f"<p>{content}</p>"

    if memory_data:
        body += """
        <label class="toggle">
            <input type="checkbox" />
            <span class="pill-label">Red Pill</span>
        </label>
        <div class="reveal">
            <p><strong>Why this is false:</strong> {why_this_is_false}</p>
            <p><strong>Rationale:</strong> {rationale}</p>
        </div>
        """.format(
            why_this_is_false=memory_data.get('why_this_is_false', ''),
            rationale=memory_data.get('rationale', ''),
        )

    body += "</div>"
    return body


def main() -> None:
    diary_entries = []
    for path in ['test_data/entries_before.md', 'test_data/entries_after.md']:
        diary_entries.extend(parse_diary(Path(path)))

    timeline = build_timeline(diary_entries, [])
    gaps = detect_gaps(timeline, min_days=14)

    cards: list[str] = []
    for entry in timeline:
        cards.append(_card_html('Diary', entry['date'], entry['content']))

    for index, gap in enumerate(gaps):
        memory = STUB_MEMORIES[index % len(STUB_MEMORIES)]
        fabricated_date = memory['date']
        cards.append(
            _card_html(
                'Fabricated Memory',
                fabricated_date,
                memory['memory_text'],
                memory_data=memory,
                is_fabricated=True,
            )
        )

    if not gaps:
        for memory in STUB_MEMORIES:
            cards.append(_card_html('Stub Memory', memory['date'], memory['memory_text'], memory_data=memory, is_fabricated=True))

    output_dir = repo_root / 'output'
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / 'gallery.html'

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Apophenic Memory: 2012</title>
        <style>
            :root {{
                --bg: #0f1115;
                --panel: #171b22;
                --panel-alt: #1d2430;
                --card: #121821;
                --border: #2a3240;
                --text: #edf2ff;
                --muted: #a9b5c7;
                --accent: #9ad0ff;
                --accent-strong: #6ab7ff;
                --danger: #ffb3b3;
            }}

            * {{ box-sizing: border-box; }}

            body {{
                margin: 0;
                font-family: Arial, Helvetica, sans-serif;
                background: var(--bg);
                color: var(--text);
                line-height: 1.5;
            }}

            .page {{
                max-width: 1000px;
                margin: 0 auto;
                padding: 32px 20px 48px;
            }}

            h1 {{
                margin: 0 0 12px;
                font-size: 2.5rem;
                letter-spacing: 0.04em;
            }}

            .subhead {{
                margin: 0 0 24px;
                color: var(--muted);
            }}

            .timeline {{
                display: flex;
                flex-direction: column;
                gap: 18px;
            }}

            .card {{
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 18px 20px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
            }}

            .card.fabricated {{
                border-color: var(--accent-strong);
                background: linear-gradient(180deg, rgba(106, 183, 255, 0.12), rgba(17, 24, 32, 0.95));
            }}

            .card-header {{
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: center;
                margin-bottom: 12px;
            }}

            .badge {{
                display: inline-block;
                background: var(--panel-alt);
                border: 1px solid var(--border);
                border-radius: 999px;
                padding: 6px 10px;
                font-size: 0.76rem;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: var(--accent);
            }}

            .date {{
                color: var(--muted);
                font-size: 0.88rem;
            }}

            p {{
                margin: 0;
            }}

            .toggle {{
                display: block;
                margin-top: 16px;
                padding-top: 12px;
                border-top: 1px solid var(--border);
            }}

            .toggle input {{
                margin-right: 8px;
            }}

            .pill-label {{
                cursor: pointer;
                color: var(--danger);
                font-weight: 700;
            }}

            .reveal {{
                display: none;
                margin-top: 12px;
                padding: 12px 14px;
                background: rgba(255,255,255,0.02);
                border-left: 3px solid var(--accent);
                border-radius: 8px;
            }}

            .toggle input:checked ~ .reveal {{
                display: block;
            }}
        </style>
    </head>
    <body>
        <div class="page">
            <h1>Apophenic Memory: 2012</h1>
            <p class="subhead">Timeline + fabricated gap memory</p>

            <div class="timeline">
                {' '.join(cards)}
            </div>
        </div>
    </body>
    </html>
    """

    output_path.write_text(html.strip() + '\n', encoding='utf-8')
    print(f"Gallery generated: {output_path}")


if __name__ == '__main__':
    main()
