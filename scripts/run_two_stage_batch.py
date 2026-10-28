import json
import sys
from collections import Counter
from pathlib import Path

# Ensure package root is in python path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from apophenic_memory.liar.two_stage import generate_two_stage


def main() -> None:
    context_path = REPO_ROOT / "test_data" / "gap_2012_03.json"
    if not context_path.exists():
        context_path = Path("test_data/gap_2012_03.json")
    context = json.loads(context_path.read_text(encoding="utf-8"))

    total_runs = 10
    recent_scenes: list[str] = []
    runs_data = []

    print(f"Starting batch evaluation: {total_runs} runs using live Ollama...", flush=True)

    for run_idx in range(1, total_runs + 1):
        print(f"Executing run {run_idx}/{total_runs}...", end=" ", flush=True)
        result = generate_two_stage(context, recent_scenes=recent_scenes)

        blueprint = getattr(result, "blueprint", {}) or {}
        scene_type = blueprint.get("scene_type", "unknown")
        if scene_type and scene_type != "unknown":
            recent_scenes.append(scene_type)

        actual_wc = result.memory.word_count
        target_wc = blueprint.get("target_length_words", 110)

        # Check if generation_status == "completed"
        status = result.memory.generation_status
        passed_all_constraints = (status == "completed")

        failed_constraints = [
            cr["constraint_id"]
            for cr in result.memory.constraint_results
            if not cr.get("passed", False)
        ]

        runs_data.append({
            "run": run_idx,
            "scene_type": scene_type,
            "word_count_actual": actual_wc,
            "word_count_target": target_wc,
            "passed_all_constraints": passed_all_constraints,
            "failed_constraints": failed_constraints,
            "status": status,
        })
        print(f"done (scene={scene_type}, wc={actual_wc}/{target_wc}, status={status})")

    # Save detailed JSON output for records
    results_path = REPO_ROOT / "test_data" / "two_stage_run_results.json"
    results_path.write_text(json.dumps(runs_data, indent=2), encoding="utf-8")

    # Print Markdown table
    print("\n## Evaluation Results\n")
    print("| Run # | Scene Type | Word Count | Status | Failed Constraints |")
    print("|-------|------------|------------|--------|--------------------|")
    for r in runs_data:
        failed_str = ", ".join(r["failed_constraints"]) if r["failed_constraints"] else "None"
        wc_str = f"{r['word_count_actual']} / {r['word_count_target']}"
        print(f"| {r['run']} | {r['scene_type']} | {wc_str} | {r['status']} | {failed_str} |")

    # Metrics calculation
    successful_runs = sum(1 for r in runs_data if r["passed_all_constraints"])
    all_failed_ids = [fid for r in runs_data for fid in r["failed_constraints"]]
    if all_failed_ids:
        most_common_failure = Counter(all_failed_ids).most_common(1)[0][0]
    else:
        most_common_failure = "None"

    print("\n### Final Metrics")
    print(f"- Total runs: {total_runs}")
    print(f"- Success rate (passed all constraints without warnings): {successful_runs}/{total_runs}")
    print(f"- Most common failure constraint: {most_common_failure}\n")


if __name__ == "__main__":
    main()
