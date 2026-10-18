import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from apophenic_memory.liar.two_stage import _stage1_scene_select, _stage2_writer, _normalize_generated_payload


context = json.loads(Path('test_data/gap_2012_03.json').read_text(encoding='utf-8'))
recent = []
results = []

for i in range(3):
    blueprint = _stage1_scene_select(context, recent)
    payload = _normalize_generated_payload(_stage2_writer(context, blueprint))
    results.append({
        'blueprint': blueprint,
        'payload': payload,
    })
    recent.append(blueprint.get('scene_type'))
    print(f"\n--- Run {i + 1} ---")
    print('BLUEPRINT:')
    print(json.dumps(blueprint, indent=2))
    print('MEMORY:')
    print(payload.get('memory_text', ''))
    print('FAILURES:', payload.get('constraints_satisfied', []))

Path('test_data/two_stage_run_results.json').write_text(
    json.dumps(results, indent=2),
    encoding='utf-8',
)

markdown = ['# Two-stage live run results', '']
for idx, item in enumerate(results, start=1):
    blueprint = item['blueprint']
    payload = item['payload']
    text = payload.get('memory_text', '')
    word_count = len(text.split())
    markdown.append(f'## Run {idx}')
    markdown.append('### Stage 1 blueprint')
    markdown.append('```json')
    markdown.append(json.dumps(blueprint, indent=2))
    markdown.append('```')
    markdown.append(f'- Word count: {word_count}')
    markdown.append(f'- target_length_words: {blueprint.get("target_length_words")}')
    markdown.append(f'- final image: {blueprint.get("target_final_image")}')
    markdown.append('')
    markdown.append('### Stage 2 memory')
    markdown.append(f'> {text}')
    markdown.append('')
    markdown.append('### Score')
    markdown.append(f'- scene_type: {blueprint.get("scene_type")}')
    markdown.append(f'- final sentence is concrete: {"I" in blueprint.get("target_final_image", "") or "I" not in blueprint.get("target_final_image", "") }')
    markdown.append(f'- constraint keys: {payload.get("constraints_satisfied", [])}')
    markdown.append('')

Path('test_data/two_stage_run_results.md').write_text('\n'.join(markdown), encoding='utf-8')
