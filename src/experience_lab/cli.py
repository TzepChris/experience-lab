"""Command-line interface for demo, bounded benchmark, and summary report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from experience_lab.artifact import build_v01_artifact
from experience_lab.checkpoint_eval import run_checkpoint_benchmark
from experience_lab.checkpoint_report import write_checkpoint_report
from experience_lab.evaluation import load_config, render_ansi, run_benchmark
from experience_lab.report import write_diagnostic_report
from experience_lab.reprobe_report import write_reprobe_report
from experience_lab.serialization import write_json


def _print(line: str) -> None:
    print(line)


def cmd_demo(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.seed is not None:
        config["seeds"] = [args.seed]
    output = Path(args.output or config.get("output") or "results/demo")
    print("Experience Lab demo (public observation only in the grid below).")
    print("Evaluator footnote with the hidden rule is printed after the run, not to the learner.")
    summary = run_benchmark(
        config,
        output_dir=output,
        max_wall_seconds=config.get("max_wall_seconds", 30),
        render=True,
        on_render=_print,
    )
    runs = summary["runs"]
    if runs:
        rule = runs[0]["rule"]
        print()
        print(f"[evaluator only] hidden rule for this demo: {rule}")
        print(f"[evaluator only] run status: {runs[0]['status']}")
        print(f"[evaluator only] exact rule recovery: {runs[0].get('exact_rule_recovery')}")
    print(f"wall_seconds={summary['wall_seconds']:.4f} status={summary['status']}")
    print(f"logs: {output / 'events.jsonl'}")
    return 0 if summary["status"] == "completed" else 1


def cmd_benchmark(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output = Path(args.output or config.get("output") or "results/pilot")
    wall = args.max_wall_seconds
    if str(config.get("experiment") or "").startswith("checkpoint"):
        summary = run_checkpoint_benchmark(
            config,
            output_dir=output,
            max_wall_seconds=wall,
            render=False,
        )
    else:
        summary = run_benchmark(
            config,
            output_dir=output,
            max_wall_seconds=wall,
            render=False,
        )
    skip = {"runs", "pairs", "checkpoint_report", "reprobe_report"}
    print(json.dumps({k: v for k, v in summary.items() if k not in skip}, indent=2, sort_keys=True))
    print(f"full summary: {output / 'summary.json'}")
    print(f"events: {output / 'events.jsonl'}")
    print(f"manifest: {output / 'manifest.json'}")
    audit_path = output / "random_informative_audit.json"
    if audit_path.exists():
        print(f"random-informative audit: {audit_path}")
    reprobe_path = output / "reprobe_report.json"
    if reprobe_path.exists():
        print(f"reprobe report: {reprobe_path}")
    checkpoint_path = output / "checkpoint_report.json"
    if checkpoint_path.exists():
        print(f"checkpoint report: {checkpoint_path}")
    bucket_path = output / "bucket_assignments.json"
    if bucket_path.exists():
        print(f"bucket assignments: {bucket_path}")
    return 0 if summary["status"] == "completed" else 1


def cmd_report(args: argparse.Namespace) -> int:
    input_dir = Path(args.input)
    summary_path = input_dir / "summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    max_steps = 256
    manifest: dict = {}
    manifest_path = input_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        max_steps = int((manifest.get("config") or {}).get("max_episode_steps", 256))
    if payload.get("pairs") is not None:
        prefixes = tuple(
            int(k)
            for k in (manifest.get("config") or {}).get("prefixes") or (1, 2, 5, 10)
        )
        report = write_checkpoint_report(payload, input_dir, max_steps, prefixes)
        printable = {
            "status": payload.get("status"),
            "wall_seconds": payload.get("wall_seconds"),
            "completed_pairs": payload.get("completed_pairs"),
            "total_scheduled_pairs": payload.get("total_scheduled_pairs"),
            "n_checkpoints": len(report.get("by_checkpoint") or []),
            "starting_conditions": sorted((report.get("by_starting_condition") or {}).keys()),
            "note": report.get("note"),
        }
        print(json.dumps(printable, indent=2, sort_keys=True))
        print(f"checkpoint report: {input_dir / 'checkpoint_report.json'}")
        return 0
    report = write_diagnostic_report(payload, input_dir, max_steps)
    methods = set()
    for run in payload.get("runs") or []:
        methods.add(str(run.get("method")))
    if "active_reprobe_retained" in methods:
        prefixes = tuple(
            int(k)
            for k in (manifest.get("config") or {}).get("prefixes") or (1, 2, 5, 10)
        )
        write_reprobe_report(payload, input_dir, max_steps, prefixes)
    printable = {
        "status": payload.get("status"),
        "wall_seconds": payload.get("wall_seconds"),
        "completed_runs": payload.get("completed_runs"),
        "total_scheduled_runs": payload.get("total_scheduled_runs"),
        "n_instances": report.get("n_instances"),
        "n_physical_problems": report.get("n_physical_problems"),
        "n_differences": report.get("n_differences"),
        "pooled_method_means": report.get("pooled_method_means"),
        "note": report.get("note"),
    }
    if args.output:
        out = Path(args.output)
        if out.suffix.lower() == ".json":
            write_json(out, report)
        else:
            out.mkdir(parents=True, exist_ok=True)
            write_json(out / "report.json", report)
    print(json.dumps(printable, indent=2, sort_keys=True))
    print(f"instance table and traces: {input_dir / 'report.json'}")
    return 0


def cmd_artifact(args: argparse.Namespace) -> int:
    payload = build_v01_artifact(
        holdout_dir=Path(args.holdout),
        development_dir=Path(args.development),
        output_dir=Path(args.output),
    )
    analysis = payload["analysis"]
    rec = analysis["reconcile"]
    boot = analysis["bootstrap"]["intervals"]
    xor_trace = payload["xor_trace"]
    printable = {
        "output_dir": payload["output_dir"],
        "batch_status": analysis["batch_status"],
        "n_maps": analysis["n_maps"],
        "n_cells": analysis["n_cells"],
        "reconcile": rec,
        "mean_later_c": boot["mean_later_c"],
        "mean_delta_c_minus_a": boot["mean_delta_c_minus_a"],
        "xor_checkpoint_id": xor_trace["checkpoint_id"],
        "xor_k10_later": {
            "A": xor_trace["k10_later_a"],
            "B": xor_trace["k10_later_b"],
            "C": xor_trace["k10_later_c"],
        },
        "note": "Tables and figures rebuilt from saved summaries. A/B/C were not rerun.",
    }
    print(json.dumps(printable, indent=2, sort_keys=True))
    print(f"tables: {Path(args.output) / 'tables.md'}")
    print(f"figures: {Path(args.output) / 'figures'}")
    return 0 if all(rec.values()) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="experience-lab")
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser("demo", help="run a tiny rendered trace")
    demo.add_argument("--config", default="configs/smoke.yaml")
    demo.add_argument("--seed", type=int, default=None)
    demo.add_argument("--output", default=None)
    demo.set_defaults(func=cmd_demo)

    bench = sub.add_parser("benchmark", help="run a configured batch")
    bench.add_argument("--config", default="configs/pilot.yaml")
    bench.add_argument("--output", default=None)
    bench.add_argument("--max-wall-seconds", type=float, default=None)
    bench.set_defaults(func=cmd_benchmark)

    report = sub.add_parser("report", help="print an existing summary")
    report.add_argument("--input", required=True)
    report.add_argument("--output", default=None)
    report.set_defaults(func=cmd_report)

    artifact = sub.add_parser(
        "artifact",
        help="rebuild v0.1 tables and figures from saved summaries",
    )
    artifact.add_argument("--holdout", default="results/checkpoint_geometry_holdout")
    artifact.add_argument("--development", default="results/checkpoint_ul_stopping")
    artifact.add_argument("--output", default="docs/v0.1")
    artifact.set_defaults(func=cmd_artifact)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
