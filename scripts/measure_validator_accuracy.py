#!/usr/bin/env python3
"""scripts/measure_validator_accuracy.py

Evaluates the deterministic validator suite against a labeled golden dataset.
Measures True Positives, True Negatives, False Positives, False Negatives,
Precision, and Recall.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from apophenic_memory.liar.constraints import (
    OutputContractError,
    validate,
    validate_closing,
    validate_contract,
    validate_era,
)


def evaluate_memory(item: dict, context: dict) -> tuple[bool, list[str]]:
    """Runs a memory through all deterministic validators and returns (passed, failures)."""
    failures: list[str] = []

    payload = {
        "memory_text": item.get("memory_text", ""),
        "why_this_is_false": item.get("why_this_is_false", "Synthetic test memory."),
        "rationale": item.get("rationale", "Test rationale."),
        "constraints_satisfied": item.get("constraints_satisfied", ["C1", "C2", "C3", "C4", "C5", "C6"]),
    }

    # 1. Structural Output Contract Validator
    try:
        validate_contract(json.dumps(payload))
    except OutputContractError as exc:
        failures.append(f"CONTRACT: {exc}")

    # 2. Main Constraint Validator (C1-C6, C_CLOSING, C_DIVERSITY, C_ERA)
    constraint_results = validate(payload, context)
    for res in constraint_results:
        if not res.passed:
            failures.append(f"{res.constraint_id}: {res.message}")

    # 3. Explicit Closing Validator check (ensure standalone coverage)
    closing_results = validate_closing(payload)
    for res in closing_results:
        if not res.passed and not any(f.startswith("C_CLOSING:") for f in failures):
            failures.append(f"{res.constraint_id}: {res.message}")

    # 4. Explicit Era Validator check (ensure standalone coverage)
    era_results = validate_era(payload, context)
    for res in era_results:
        if not res.passed and not any(f.startswith("C_ERA:") for f in failures):
            failures.append(f"{res.constraint_id}: {res.message}")

    passed = (len(failures) == 0)
    return passed, failures


def main() -> None:
    dataset_path = REPO_ROOT / "test_data" / "validator_golden_dataset.json"
    context_path = REPO_ROOT / "test_data" / "gap_2012_03.json"

    if not dataset_path.exists():
        print(f"Error: Golden dataset not found at {dataset_path}")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        golden_dataset = json.load(f)

    context = {}
    if context_path.exists():
        with open(context_path, "r", encoding="utf-8") as f:
            context = json.load(f)

    print(f"Loaded {len(golden_dataset)} samples from {dataset_path.name}")
    print("=" * 80)
    print(f"{'ID':<30} | {'Expected':<8} | {'Actual':<8} | {'Result':<6} | {'Failures'}")
    print("-" * 80)

    tp = 0  # Invalid memory correctly failed
    tn = 0  # Valid memory correctly passed
    fp = 0  # Valid memory incorrectly failed
    fn = 0  # Invalid memory incorrectly passed

    for item in golden_dataset:
        item_id = item.get("id", "sample")
        expected_pass = item["expected_pass"]
        actual_pass, failures = evaluate_memory(item, context)

        if not expected_pass and not actual_pass:
            classification = "TP"
            tp += 1
        elif expected_pass and actual_pass:
            classification = "TN"
            tn += 1
        elif expected_pass and not actual_pass:
            classification = "FP"
            fp += 1
        else:
            classification = "FN"
            fn += 1

        fail_summary = "; ".join(failures) if failures else "None"
        exp_str = "PASS" if expected_pass else "FAIL"
        act_str = "PASS" if actual_pass else "FAIL"
        print(f"{item_id:<30} | {exp_str:<8} | {act_str:<8} | {classification:<6} | {fail_summary}")

    total = len(golden_dataset)
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    accuracy = ((tp + tn) / total) if total > 0 else 0.0
    fpr = (fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    print("=" * 80)
    print("Validator Evaluation Summary")
    print(f"- Total Samples: {total}")
    print(f"- True Positives (correctly failed): {tp}")
    print(f"- True Negatives (correctly passed): {tn}")
    print(f"- False Positives (incorrectly failed): {fp}")
    print(f"- False Negatives (incorrectly passed): {fn}")
    print(f"- Accuracy: {accuracy * 100:.1f}%")
    print(f"- Precision: {precision * 100:.1f}%")
    print(f"- Recall: {recall * 100:.1f}%")
    print(f"- False Positive Rate: {fpr * 100:.1f}%")


if __name__ == "__main__":
    main()
