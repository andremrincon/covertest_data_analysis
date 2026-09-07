#!/usr/bin/env python3
"""
extract.py -- Rebuild the two consolidated CSVs (executions.csv, steps.csv)
directly from the raw *_synthesis_metrics.json files produced by ANOMTOOL.

This is the entry point of the replication package's analysis pipeline:

    raw JSON (generated_tests/sequence_*/run_*/<seed>/<project>/ts01_synthesis_metrics.json)
        |
        v
    extract.py  ->  data/executions.csv, data/steps.csv
        |
        v
    make_tables.py   ->  Tables 3-5
    make_figures.py  ->  Figures 3-4

Usage:
    python3 extract.py --root /path/to/generated_tests --out data/

If --root is not given, the script looks for a "generated_tests" directory
next to this script, then falls back to the environment variable
ANOMTOOL_DATA_ROOT.
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter

import pandas as pd

# Short labels used throughout the tables/figures, matching the paper's
# qwen/qwen3.7-plus, openai/gpt-5-mini, z-ai/glm-5.2.
SHORT = {
    "qwen/qwen3.7-plus": "qwen3.7-plus",
    "openai/gpt-5-mini": "gpt-5-mini",
    "z-ai/glm-5.2": "glm-5.2",
}

# The two executions whose position-1 metrics file was overwritten by a
# retried run (see README.md, "Known data issue"). Their step-1 and
# execution-level C1 are corrected to the value confirmed by the seven
# sibling runs of the same (sequence, project) cell.
KNOWN_BAD = {
    ("sequence_06", "run_01", 450, "features-service"),
    ("sequence_06", "run_03", 767, "features-service"),
}
REPAIRED_C1 = 80.96


def find_default_root(script_dir):
    candidate = os.path.join(script_dir, "generated_tests")
    if os.path.isdir(candidate):
        return candidate
    env = os.environ.get("ANOMTOOL_DATA_ROOT")
    if env and os.path.isdir(env):
        return env
    return None


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=None,
                     help="Path to the generated_tests/ directory "
                          "(contains sequence_01 .. sequence_06).")
    ap.add_argument("--out", default=os.path.join(script_dir, "data"),
                     help="Output directory for executions.csv / steps.csv.")
    ap.add_argument("--repair", action="store_true", default=True,
                     help="Repair the two known mis-logged records "
                          "(default: on). Use --no-repair to keep raw values.")
    ap.add_argument("--no-repair", dest="repair", action="store_false")
    args = ap.parse_args()

    root = args.root or find_default_root(script_dir)
    if root is None or not os.path.isdir(root):
        sys.exit(
            "Could not find the raw data directory. Pass it explicitly:\n"
            "    python3 extract.py --root /path/to/generated_tests"
        )

    pattern = os.path.join(root, "sequence_*", "run_*", "*", "*",
                            "ts01_synthesis_metrics.json")
    files = sorted(glob.glob(pattern))
    if not files:
        sys.exit(f"No ts01_synthesis_metrics.json files found under {root}")
    print(f"[extract] found {len(files)} execution files under {root}")

    erows, srows, anomalies = [], [], []

    for f in files:
        rel = os.path.relpath(f, root).split(os.sep)
        seq, run, seed_s, proj = rel[0], rel[1], rel[2], rel[3]
        seed = int(seed_s)
        d = json.load(open(f))
        steps = d["steps"]
        tot = d["totals"]

        # ---- consistency checks against the raw file itself ----
        roi = [s.get("report_order_index") for s in steps]
        fni = [s.get("filename_index") for s in steps]
        if roi != sorted(roi):
            anomalies.append(("steps_array_unsorted", rel, roi))
        if roi != fni:
            anomalies.append(("roi_ne_filename_index", rel, roi, fni))
        if len(steps) != 3:
            anomalies.append(("n_steps", rel, len(steps)))
        if d.get("warnings"):
            anomalies.append(("warnings", rel, d["warnings"]))
        if d.get("gaps"):
            anomalies.append(("gaps", rel, d["gaps"]))

        order = [SHORT[s["generation_model"]] for s in steps]

        for k in range(len(steps) - 1):
            if abs(steps[k]["final_coverage"] - steps[k + 1]["initial_coverage"]) > 1e-6:
                anomalies.append(("chain_break", rel, k,
                                   steps[k]["final_coverage"],
                                   steps[k + 1]["initial_coverage"]))
        if abs(steps[0]["initial_coverage"] - tot["initial_coverage_cycle"]) > 1e-6:
            anomalies.append(("T0_mismatch", rel,
                               steps[0]["initial_coverage"],
                               tot["initial_coverage_cycle"]))
        if abs(steps[-1]["final_coverage"] - tot["final_coverage_cycle"]) > 1e-6:
            anomalies.append(("C3_mismatch", rel,
                               steps[-1]["final_coverage"],
                               tot["final_coverage_cycle"]))

        sgs = sum(s["coverage_gain"] for s in steps)
        if abs(sgs - tot["coverage_gain_cycle"]) > 1e-3:
            anomalies.append(("gain_reconcile", rel, sgs, tot["coverage_gain_cycle"]))

        ct = sum(s["llm_totals"]["cost_total"] for s in steps)
        tk = sum(s["llm_totals"]["total_tokens"] for s in steps)
        if abs(ct - tot["total_cost"]) > 1e-6:
            anomalies.append(("cost_reconcile", rel, ct, tot["total_cost"]))
        if tk != tot["total_tokens"]:
            anomalies.append(("token_reconcile", rel, tk, tot["total_tokens"]))

        flagged = (seq, run, seed, proj) in KNOWN_BAD

        c1 = steps[0]["final_coverage"]
        if flagged and args.repair:
            c1 = REPAIRED_C1

        erows.append(dict(
            sequence=seq, seq_num=int(seq.split("_")[1]), run=run, seed=seed,
            project=proj, seq_label=" -> ".join(order),
            m1=order[0], m2=order[1], m3=order[2],
            T0=tot["initial_coverage_cycle"],
            C1=c1,
            C2=steps[1]["final_coverage"],
            C3=tot["final_coverage_cycle"],
            gain=tot["coverage_gain_cycle"],
            time_min=tot["total_execution_time_seconds"] / 60.0,
            tokens=tot["total_tokens"], cost=tot["total_cost"],
            requests=tot["total_requests"],
            flagged=flagged,
        ))

        for pos, s in enumerate(steps, start=1):
            fin = s["final_coverage"]
            gain = s["coverage_gain"]
            if flagged and pos == 1 and args.repair:
                fin = REPAIRED_C1
                gain = REPAIRED_C1 - s["initial_coverage"]
            srows.append(dict(
                sequence=seq, seq_num=int(seq.split("_")[1]), run=run,
                seed=seed, project=proj, position=pos,
                model=SHORT[s["generation_model"]],
                init=s["initial_coverage"], fin=fin, gain=gain,
                tokens=s["llm_totals"]["total_tokens"],
                cost=s["llm_totals"]["cost_total"],
                requests=s["llm_totals"]["total_requests"],
                time_min=s["execution_time_seconds"] / 60.0,
                flagged=flagged,
            ))

    E = pd.DataFrame(erows)
    S = pd.DataFrame(srows)

    os.makedirs(args.out, exist_ok=True)
    e_path = os.path.join(args.out, "executions.csv")
    s_path = os.path.join(args.out, "steps.csv")
    E.to_csv(e_path, index=False)
    S.to_csv(s_path, index=False)

    print(f"[extract] executions: {len(E)}  steps: {len(S)}")
    print(f"[extract] wrote {e_path}")
    print(f"[extract] wrote {s_path}")
    print(f"[extract] repair applied: {args.repair}  "
          f"(flagged executions: {E.flagged.sum()})")

    print("\n[extract] --- design completeness ---")
    print(E.groupby("sequence").size().to_string())
    n_cells = len(E.drop_duplicates(["sequence", "project", "seed", "run"]))
    print(f"cells (sequence x project x seed x run) unique: {n_cells}  "
          f"(expected 270)")

    print("\n[extract] --- anomalies found in raw JSON ---")
    if not anomalies:
        print("none")
    else:
        print(Counter(a[0] for a in anomalies))
        for a in anomalies[:15]:
            print(" ", a)
        print("See README.md, 'Known data issue', for how the two "
              "mis-logged records are handled.")


if __name__ == "__main__":
    main()
