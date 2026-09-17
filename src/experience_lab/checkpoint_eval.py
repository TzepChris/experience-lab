"""Paired checkpoint experiment: exploit, complete-target probe, and U/L stop.

Episode 0 is collected once from a source learner. Forks A, B, and optional C
copy that public belief. Oracle numbers are evaluator-only and never enter
learner decisions. Method C is a hand-designed stopping rule, not a learned
policy.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from experience_lab.agents import ModelBasedAgent, Selector, make_agent, make_checkpoint_fork
from experience_lab.checkpoint_report import write_checkpoint_report
from experience_lab.evaluation import (
    OracleController,
    _make_env,
    build_manifest,
    hardware_summary,
    physical_problem_id,
    problem_id,
    run_episode,
)
from experience_lab.layouts import get_layout, with_switch_permutation
from experience_lab.rules import permute_rule_name
from experience_lab.serialization import append_jsonl, write_json


FORK_EXPLOIT = "checkpoint_exploit"
FORK_COMPLETE = "checkpoint_complete_reprobe"
FORK_UL = "checkpoint_ul_stopping"
DEFAULT_PREFIXES = (1, 2, 5, 10)


def classify_starting_condition(source_method: str, ep0_cost: int, oracle_ep0: int | None) -> str:
    """Evaluator-only acquisition bucket. Compares episode-0 cost to oracle episode 0.

    This is not the current conservative exploit-plan length U. Bucket labels are
    never passed into learner decisions.
    """
    expensive = oracle_ep0 is not None and ep0_cost > oracle_ep0
    if source_method.startswith("systematic"):
        return "expensive_systematic" if expensive else "cheap_systematic_control"
    if source_method.startswith("active"):
        return "cheap_active" if not expensive else "expensive_active_control"
    return "other_control"


def _source_selector(source_method: str) -> Selector:
    if source_method.startswith("systematic"):
        return "systematic"
    if source_method.startswith("random_informative"):
        return "random_informative"
    return "active"


def iter_checkpoint_schedule(config: dict[str, Any]) -> list[tuple[str, str, tuple[int, ...], int, str]]:
    layout_names = list(config.get("layouts") or [config["layout"]])
    raw_perms = config.get("switch_permutations") or [[0, 1]]
    perms = [tuple(int(i) for i in perm) for perm in raw_perms]
    sources = list(config.get("source_methods") or ["systematic_retained", "active_retained"])
    return [
        (layout_name, rule_name, perm, int(seed), source)
        for layout_name in layout_names
        for rule_name in config["rules"]
        for perm in perms
        for seed in config["seeds"]
        for source in sources
    ]


def _oracle_episode0(
    layout,
    rule_name: str,
    max_steps: int,
    expansion_cap: int,
    deadline: float | None,
) -> dict[str, Any]:
    env = _make_env(layout, rule_name, max_steps)
    controller = OracleController(layout, env._hidden_rules, expansion_cap)
    return run_episode(
        env,
        controller,
        run_id=f"oracle|{layout.geometry}|{rule_name}",
        episode_index=0,
        log_path=None,
        render=False,
        log_every_step=False,
        deadline=deadline,
    )


def run_checkpoint_benchmark(
    config: dict[str, Any],
    *,
    output_dir: Path | None = None,
    max_wall_seconds: float | None = None,
    render: bool | None = None,
    on_render: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    del render, on_render
    include_ul = bool(config.get("include_ul_stopping", False)) or str(
        config.get("experiment") or ""
    ) == "checkpoint_ul_stopping"
    default_output = (
        "results/checkpoint_ul_stopping" if include_ul else "results/checkpoint_complete_probe"
    )
    output = Path(output_dir or config.get("output") or default_output)
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "events.jsonl"
    checkpoint_path = output / "checkpoints.jsonl"
    if log_path.exists():
        log_path.unlink()
    if checkpoint_path.exists():
        checkpoint_path.unlink()
    wall = float(
        max_wall_seconds
        if max_wall_seconds is not None
        else config.get("max_wall_seconds", 120)
    )
    deadline = time.perf_counter() + wall
    started = time.perf_counter()
    manifest = build_manifest(config, output, "running")
    write_json(output / "manifest.json", manifest)

    later_n = int(config.get("later_episodes") or config.get("episodes_per_run") or 10)
    max_steps = int(config["max_episode_steps"])
    expansion_cap = int(config["planner_expansion_cap"])
    prefixes = tuple(int(k) for k in config.get("prefixes") or DEFAULT_PREFIXES)
    schedule = iter_checkpoint_schedule(config)
    oracle_cache: dict[tuple[str, str, tuple[int, ...]], dict[str, Any]] = {}
    pairs: list[dict[str, Any]] = []
    interrupted = False

    for layout_name, requested_rule, perm, seed, source_method in schedule:
        if time.perf_counter() >= deadline:
            interrupted = True
            pairs.append(
                {
                    "checkpoint_id": f"{problem_id(layout_name, requested_rule, perm)}|seed{seed}|{source_method}",
                    "status": "interrupted_time",
                    "source_method": source_method,
                    "layout": layout_name,
                    "requested_rule": requested_rule,
                    "permutation": list(perm),
                    "seed": seed,
                    "episode0": None,
                    "forks": {},
                }
            )
            continue
        base_layout = get_layout(layout_name)
        layout = with_switch_permutation(base_layout, perm)
        applied_rule = permute_rule_name(requested_rule, layout.n_switches, perm)
        cache_key = (layout_name, applied_rule, perm)
        if cache_key not in oracle_cache:
            oracle_cache[cache_key] = _oracle_episode0(
                layout, applied_rule, max_steps, expansion_cap, deadline
            )
        oracle_ep = oracle_cache[cache_key]
        oracle_ep0 = (
            int(oracle_ep["steps"])
            if oracle_ep.get("status") == "completed" and oracle_ep.get("success")
            else None
        )

        env = _make_env(layout, applied_rule, max_steps)
        source = make_agent(layout, source_method, seed, expansion_cap)
        checkpoint_id = f"{problem_id(layout_name, requested_rule, perm)}|seed{seed}|{source_method}"
        ep0 = run_episode(
            env,
            source,
            run_id=f"{source_method}|{checkpoint_id}|episode0",
            episode_index=0,
            log_path=log_path,
            render=False,
            log_every_step=bool(config.get("log_every_step", False)),
            deadline=deadline,
        )
        if ep0["status"] != "completed":
            interrupted = interrupted or ep0["status"] == "interrupted_time"
            pairs.append(
                {
                    "checkpoint_id": checkpoint_id,
                    "status": ep0["status"],
                    "source_method": source_method,
                    "layout": layout_name,
                    "requested_rule": requested_rule,
                    "rule": applied_rule,
                    "permutation": list(perm),
                    "problem_id": problem_id(layout_name, requested_rule, perm),
                    "physical_problem_id": physical_problem_id(layout_name, requested_rule),
                    "seed": seed,
                    "episode0": ep0,
                    "oracle_episode0_cost": oracle_ep0,
                    "forks": {},
                }
            )
            continue

        if not isinstance(source, ModelBasedAgent):
            raise TypeError("checkpoint source must be a model-based agent")
        belief_snapshot = source.belief.snapshot()
        starting = classify_starting_condition(
            source_method, int(ep0["steps"]), oracle_ep0
        )
        checkpoint_public = {
            "checkpoint_id": checkpoint_id,
            "source_method": source_method,
            "source_selector": _source_selector(source_method),
            "layout": layout_name,
            "requested_rule": requested_rule,
            "permutation": list(perm),
            "seed": seed,
            "episode0_steps": ep0["steps"],
            "episode0_success": ep0["success"],
            "belief": belief_snapshot,
            "starting_condition": starting,
        }
        append_jsonl(checkpoint_path, checkpoint_public)

        forks: dict[str, Any] = {}
        fork_specs = [
            (FORK_EXPLOIT, False, False, False),
            (FORK_COMPLETE, True, True, False),
        ]
        if include_ul:
            fork_specs.append((FORK_UL, True, True, True))
        pair_status = "completed"
        for fork_name, optional, complete_target, hypothesis_stopping in fork_specs:
            if time.perf_counter() >= deadline:
                interrupted = True
                pair_status = "interrupted_time"
                forks[fork_name] = {"status": "interrupted_time", "episodes": []}
                continue
            fork = make_checkpoint_fork(
                layout,
                _source_selector(source_method),
                seed,
                expansion_cap,
                optional_reprobe=optional,
                complete_target_probe=complete_target,
                belief=source.belief,
                hypothesis_stopping=hypothesis_stopping,
            )
            later: list[dict[str, Any]] = []
            fork_status = "completed"
            for later_index in range(later_n):
                if time.perf_counter() >= deadline:
                    interrupted = True
                    fork_status = "interrupted_time"
                    break
                record = run_episode(
                    env,
                    fork,
                    run_id=f"{fork_name}|{checkpoint_id}",
                    episode_index=later_index + 1,
                    log_path=log_path,
                    render=False,
                    log_every_step=bool(config.get("log_every_step", False)),
                    deadline=deadline,
                )
                record["later_index"] = later_index
                later.append(record)
                if record["status"] != "completed":
                    fork_status = record["status"]
                    interrupted = interrupted or record["status"] == "interrupted_time"
                    break
            if fork_status != "completed":
                pair_status = fork_status
            forks[fork_name] = {
                "status": fork_status,
                "method": fork_name,
                "episodes": later,
                "interactions": sum(ep.get("steps", 0) for ep in later),
                "wall_seconds": sum(float(ep.get("wall_seconds") or 0) for ep in later),
            }

        pair = {
            "checkpoint_id": checkpoint_id,
            "status": pair_status,
            "source_method": source_method,
            "source_selector": _source_selector(source_method),
            "layout": layout_name,
            "requested_rule": requested_rule,
            "rule": applied_rule,
            "permutation": list(perm),
            "problem_id": problem_id(layout_name, requested_rule, perm),
            "physical_problem_id": physical_problem_id(layout_name, requested_rule),
            "seed": seed,
            "starting_condition": starting,
            "episode0": ep0,
            "episode0_cost": int(ep0["steps"]) if ep0.get("success") else max_steps,
            "oracle_episode0_cost": oracle_ep0,
            "belief_after_episode0": belief_snapshot,
            "forks": forks,
            "evaluator_only_true_rule": applied_rule,
        }
        append_jsonl(
            log_path,
            {
                "event": "checkpoint_pair_end",
                "checkpoint_id": checkpoint_id,
                "status": pair_status,
                "starting_condition": starting,
                "episode0_cost": pair["episode0_cost"],
                "oracle_episode0_cost": oracle_ep0,
            },
        )
        pairs.append(pair)

    elapsed = time.perf_counter() - started
    summary: dict[str, Any] = {
        "status": "interrupted_time" if interrupted else "completed",
        "wall_seconds": elapsed,
        "max_wall_seconds": wall,
        "completed_pairs": sum(1 for pair in pairs if pair.get("status") == "completed"),
        "total_scheduled_pairs": len(schedule),
        "hardware": hardware_summary(),
        "pairs": pairs,
        "include_ul_stopping": include_ul,
        "note": (
            "Episode 0 is shared acquisition. A, B, and optional C fork from that "
            "public belief. C is a hand-designed U vs L stopping rule, not a learned "
            "policy. Oracle episode-0 cost is evaluator-only."
        ),
    }
    report = write_checkpoint_report(summary, output, max_steps, prefixes)
    summary["checkpoint_report"] = report
    write_json(output / "summary.json", summary)
    manifest["status"] = summary["status"]
    manifest["wall_seconds"] = elapsed
    write_json(output / "manifest.json", manifest)
    return summary
