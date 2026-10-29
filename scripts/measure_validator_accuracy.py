#!/usr/bin/env python3
"""scripts/measure_validator_accuracy.py

Evaluates the deterministic validator suite against an expanded, labeled golden dataset.
Measures per-constraint and overall detection metrics:
True Positives, True Negatives, False Positives, False Negatives,
Precision, Recall, and False Positive Rate across dev and held-out test splits.

Evaluation Convention:
- Condition: The presence of a constraint violation / structural defect in the output.
- Positive Result (+): Validator flags / rejects the memory as invalid.
- Negative Result (-): Validator passes the memory as valid.
- True Positive (TP): An invalid memory correctly detected and rejected.
- True Negative (TN): A valid memory correctly passed without false rejection.
- False Positive (FP): A valid memory incorrectly flagged / rejected (Type I error).
- False Negative (FN): An invalid memory missed / passed through (Type II error).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
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

ALL_CONSTRAINTS = ["CONTRACT", "C1", "C2", "C3", "C4", "C5", "C6", "C_CLOSING", "C_ERA"]


def evaluate_memory_detailed(item: dict, context: dict) -> tuple[bool, dict[str, bool], list[str]]:
    """Runs all validators and returns:
    (overall_passed, {constraint_id: passed}, failure_messages)
    """
    failures: list[str] = []
    status_by_constraint: dict[str, bool] = {c: True for c in ALL_CONSTRAINTS}

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
        status_by_constraint["CONTRACT"] = False

    # 2. Main Constraint Validator (C1-C6, C_CLOSING, C_DIVERSITY, C_ERA)
    constraint_results = validate(payload, context)
    for res in constraint_results:
        cid = res.constraint_id
        if not res.passed:
            sanitized_msg = res.message.replace("\u2265", ">=")
            failures.append(f"{cid}: {sanitized_msg}")
            if cid in status_by_constraint:
                status_by_constraint[cid] = False
            elif cid == "C_DIVERSITY":
                status_by_constraint["C1"] = False

    # 3. Explicit Closing Validator check
    closing_results = validate_closing(payload)
    for res in closing_results:
        if not res.passed:
            status_by_constraint["C_CLOSING"] = False
            msg = f"{res.constraint_id}: {res.message.replace(chr(8805), '>=')}"
            if not any(f.startswith("C_CLOSING:") for f in failures):
                failures.append(msg)

    # 4. Explicit Era Validator check
    era_results = validate_era(payload, context)
    for res in era_results:
        if not res.passed:
            status_by_constraint["C_ERA"] = False
            msg = f"{res.constraint_id}: {res.message.replace(chr(8805), '>=')}"
            if not any(f.startswith("C_ERA:") for f in failures):
                failures.append(msg)

    overall_passed = (len(failures) == 0)
    return overall_passed, status_by_constraint, failures


def compute_metrics(tp: int, tn: int, fp: int, fn: int) -> dict[str, float]:
    total = tp + tn + fp + fn
    accuracy = ((tp + tn) / total) if total > 0 else 0.0
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else (1.0 if fp == 0 else 0.0)
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else (1.0 if fn == 0 else 0.0)
    fpr = (fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = (fn / (fn + tp)) if (fn + tp) > 0 else 0.0
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "fpr": fpr,
        "fnr": fnr,
    }


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

    print("=" * 88)
    print("DETERMINISTIC VALIDATOR ACCURACY BENCHMARK")
    print(f"Loaded {len(golden_dataset)} samples from {dataset_path.name}")
    print("Convention: Positive (+) = Invalid Memory Detected / Rejected")
    print("            Negative (-) = Valid Memory Accepted")
    print("=" * 88)

    print(f"\n{'ID':<36} | {'Split':<12} | {'Exp':<5} | {'Act':<5} | {'Res':<4} | {'Failures'}")
    print("-" * 88)

    overall_counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    split_counts = defaultdict(lambda: {"tp": 0, "tn": 0, "fp": 0, "fn": 0})
    constraint_counts = {c: {"tp": 0, "tn": 0, "fp": 0, "fn": 0} for c in ALL_CONSTRAINTS}

    for item in golden_dataset:
        item_id = item.get("id", "sample")
        split = item.get("split", "default")
        expected_pass = item["expected_pass"]
        targeted_constraints = set(item.get("targeted_constraints", []))

        actual_pass, status_by_constraint, failures = evaluate_memory_detailed(item, context)

        # Overall classification
        if not expected_pass and not actual_pass:
            classification = "TP"
            overall_counts["tp"] += 1
            split_counts[split]["tp"] += 1
        elif expected_pass and actual_pass:
            classification = "TN"
            overall_counts["tn"] += 1
            split_counts[split]["tn"] += 1
        elif expected_pass and not actual_pass:
            classification = "FP"
            overall_counts["fp"] += 1
            split_counts[split]["fp"] += 1
        else:
            classification = "FN"
            overall_counts["fn"] += 1
            split_counts[split]["fn"] += 1

        # Per-constraint accounting
        for cid in ALL_CONSTRAINTS:
            expected_c_violation = (cid in targeted_constraints)
            actual_c_flagged = not status_by_constraint[cid]

            if expected_c_violation and actual_c_flagged:
                constraint_counts[cid]["tp"] += 1
            elif not expected_c_violation and not actual_c_flagged:
                constraint_counts[cid]["tn"] += 1
            elif not expected_c_violation and actual_c_flagged:
                constraint_counts[cid]["fp"] += 1
            else:
                constraint_counts[cid]["fn"] += 1

        exp_str = "PASS" if expected_pass else "FAIL"
        act_str = "PASS" if actual_pass else "FAIL"
        fail_summary = "; ".join(failures[:2]) if failures else "None"
        if len(failures) > 2:
            fail_summary += f" (+{len(failures) - 2} more)"
        print(f"{item_id:<36} | {split:<12} | {exp_str:<5} | {act_str:<5} | {classification:<4} | {fail_summary}")

    print("=" * 88)

    # 1. Overall Metrics
    m = compute_metrics(**overall_counts)
    total_samples = len(golden_dataset)
    print("\n### 1. Overall System-Level Performance (Detection of Invalid Outputs)")
    print(f"- Total Samples: {total_samples}")
    print(f"- True Positives (invalid correctly rejected): {overall_counts['tp']}")
    print(f"- True Negatives (valid correctly accepted): {overall_counts['tn']}")
    print(f"- False Positives (valid incorrectly rejected): {overall_counts['fp']}")
    print(f"- False Negatives (invalid incorrectly accepted): {overall_counts['fn']}")
    print(f"- Overall Accuracy: {m['accuracy'] * 100:.1f}%")
    print(f"- Overall Precision: {m['precision'] * 100:.1f}%")
    print(f"- Overall Recall: {m['recall'] * 100:.1f}%")
    print(f"- Overall False Positive Rate: {m['fpr'] * 100:.1f}%\n")

    # 2. Performance by Dataset Split
    print("### 2. Performance by Data Split")
    print("| Split | Samples | TP | TN | FP | FN | Accuracy | Precision | Recall |")
    print("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for s_name, counts in split_counts.items():
        sm = compute_metrics(**counts)
        tot = sum(counts.values())
        print(f"| {s_name:<16} | {tot:^7} | {counts['tp']:^4} | {counts['tn']:^4} | {counts['fp']:^4} | {counts['fn']:^4} | {sm['accuracy']*100:>7.1f}% | {sm['precision']*100:>8.1f}% | {sm['recall']*100:>6.1f}% |")

    # 3. Per-Constraint Audit Matrix
    print("\n### 3. Per-Constraint Audit Matrix")
    print("| Constraint | Description | TP | TN | FP | FN | Precision | Recall | FPR |")
    print("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    desc_map = {
        "CONTRACT": "JSON schema, types & word count bounds",
        "C1": "Technology era devices & banned cliches",
        "C2": "Length bounds [80-140 words]",
        "C3": "Real people & approved entities only",
        "C4": "Plausible deniability & meta-leakage",
        "C5": "Specific anchors (number/time/quote)",
        "C6": "First-person voice (>=2 'I', no future)",
        "C_CLOSING": "Concrete ending (no emotion nouns)",
        "C_ERA": "Chronological year boundaries",
    }
    for cid in ALL_CONSTRAINTS:
        cm = compute_metrics(**constraint_counts[cid])
        desc = desc_map.get(cid, cid)
        c_counts = constraint_counts[cid]
        print(f"| {cid:<10} | {desc:<39} | {c_counts['tp']:^4} | {c_counts['tn']:^4} | {c_counts['fp']:^4} | {c_counts['fn']:^4} | {cm['precision']*100:>8.1f}% | {cm['recall']*100:>6.1f}% | {cm['fpr']*100:>5.1f}% |")

    print("\n*Note on heuristic proxies: Constraint checks like C5 (regex for digits/quotes) and C6 (regex for 'I') are deterministic syntactic proxies; they verify surface-level requirements rather than semantic depth.")


if __name__ == "__main__":
    main()
