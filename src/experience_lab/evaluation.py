"""Evaluation loop, oracle controller, and bounded pilot runner.

Oracle code is confined to this module plus planner.oracle_plan. It is never
used to select learner actions.
"""

from __future__ import annotations

import copy
import platform
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

import yaml

from experience_lab.agents import ModelBasedAgent, NoSafePlanError, make_agent
from experience_lab.belief import Belief, EmptyHypothesisError
from experience_lab.env import SwitchWorld, hidden_rule_names
from experience_lab.layouts import Layout, get_layout, probe_spur_layout, with_switch_permutation
from experience_lab.metrics import summarize_runs
from experience_lab.planner import audit_random_informative_selection, oracle_plan
from experience_lab.report import write_diagnostic_report
from experience_lab.reprobe_report import write_reprobe_report
from experience_lab.rules import TruthTable, permute_rule_name, table_by_name
from experience_lab.serialization import action_name, append_jsonl, observation_to_dict, write_json
from experience_lab.types import Action, Observation, bits_to_int


class OracleController:
    """Privileged shortest-path controller. Constructed only by the evaluator."""

    def __init__(
        self,
        layout: Layout,
        rules: tuple[TruthTable, ...],
        expansion_cap: int,
    ) -> None:
        self.layout = layout
        self._rules = rules
        self.expansion_cap = expansion_cap
        self.last_expansions = 0
        self.last_decision_meta: dict[str, Any] = {
            "plan_kind": "oracle",
            "target": None,
            "score": None,
            "hypotheses_before": None,
            "optional_reprobe": False,
        }

    def snapshot(self) -> None:
        return None

    def on_episode_start(self, observation: Observation, deadline: float | None = None, episode_index: int = 0) -> None:
        del observation, deadline, episode_index

    def update(self, observation: Observation) -> bool:
        del observation
        return False

    def select_action(
        self,
        observation: Observation,
        deadline: float | None = None,
    ) -> Action:
        bits = bits_to_int(observation.switch_bits)
        plan = oracle_plan(
            self.layout,
            observation.agent_pos,
            bits,
            self._rules,
            self.expansion_cap,
            deadline,
        )
        self.last_expansions += plan.expansions
        self.last_decision_meta = {
            "plan_kind": "oracle",
            "target": None,
            "score": None,
            "hypotheses_before": None,
            "plan_status": plan.status,
            "optional_reprobe": False,
        }
        if plan.actions is None or not plan.actions:
            raise NoSafePlanError(f"oracle failed (status={plan.status})")
        return plan.actions[0]


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _git_status() -> dict[str, Any]:
    import subprocess

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=Path(__file__).resolve().parents[2],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {"commit": None, "dirty": None}


def _dependency_versions() -> dict[str, str]:
    versions = {"python": sys.version.split()[0]}
    for name in ("numpy", "matplotlib", "pyyaml", "pytest"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def hardware_summary() -> dict[str, str]:
    return {
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "python": sys.version.split()[0],
        "machine": platform.machine(),
    }


def render_ansi(observation: Observation, title: str | None = None) -> str:
    rows = [list(row) for row in observation.static_grid]
    for (r, c), is_open in zip(observation.door_positions, observation.door_open):
        rows[r][c] = "O" if is_open else "C"
    ar, ac = observation.agent_pos
    rows[ar][ac] = "@"
    lines = []
    if title:
        lines.append(title)
    lines.extend("".join(row) for row in rows)
    switch_txt = ", ".join(
        f"{sid}={'1' if bit else '0'}"
        for sid, bit in zip(observation.switch_ids, observation.switch_bits)
    )
    door_txt = ", ".join(
        f"{did}={'open' if bit else 'closed'}"
        for did, bit in zip(observation.door_ids, observation.door_open)
    )
    lines.append(f"pos={observation.agent_pos} switches[{switch_txt}] doors[{door_txt}]")
    return "\n".join(lines)


def _make_env(layout: Layout, rule_name: str, max_steps: int) -> SwitchWorld:
    rule = table_by_name(layout.n_switches, rule_name)
    return SwitchWorld(
        layout=layout,
        _hidden_rules=tuple(rule for _ in layout.door_ids),
        max_steps=max_steps,
    )


def _make_controller(
    method: str,
    layout: Layout,
    env: SwitchWorld,
    seed: int,
    expansion_cap: int,
):
    if method == "oracle":
        return OracleController(layout, env._hidden_rules, expansion_cap)
    return make_agent(layout, method, seed, expansion_cap)


def _episode_stopping_log(controller) -> dict[str, Any] | None:
    if not getattr(controller, "hypothesis_stopping", False):
        return None
    raw = getattr(controller, "stopping_log", None)
    if not raw:
        return None
    log = copy.deepcopy(raw)
    log["extra_probe_actions"] = int(getattr(controller, "extra_probe_actions", 0) or 0)
    return log


def _controller_meta(controller) -> dict[str, Any]:
    if isinstance(controller, ModelBasedAgent) and controller.last_decision is not None:
        decision = controller.last_decision
        return {
            "plan_kind": decision.plan_kind,
            "target": decision.target,
            "score": decision.score,
            "plan_status": decision.plan_status,
            "hypotheses_before": decision.hypotheses_before,
            "optional_reprobe": decision.optional_reprobe,
        }
    if isinstance(controller, OracleController):
        return dict(controller.last_decision_meta)
    return {
        "plan_kind": None,
        "target": None,
        "score": None,
        "hypotheses_before": None,
        "optional_reprobe": False,
    }


def run_episode(
    env: SwitchWorld,
    controller,
    *,
    run_id: str,
    episode_index: int,
    log_path: Path | None,
    render: bool,
    log_every_step: bool,
    deadline: float | None,
    on_render: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    observation = env.reset()
    controller.on_episode_start(
        observation, deadline=deadline, episode_index=episode_index
    )
    return_sum = 0.0
    toggles = 0
    expansions_before = getattr(controller, "last_expansions", 0)
    status = "completed"
    terminated = False
    truncated = False
    belief_changed = False
    plan_kinds: list[str] = []
    probe_targets: list[int] = []
    first_probe_target = None
    probe_steps = 0
    task_steps = 0
    optional_reprobe = False
    identified_before = None
    if isinstance(controller, ModelBasedAgent):
        identified_before = {
            door_id: controller.belief.identified_name(door_id)
            for door_id in controller.belief.door_ids
        }

    if render and on_render:
        on_render(render_ansi(observation, title=f"{run_id} episode {episode_index} reset"))

    while True:
        if deadline is not None and time.perf_counter() >= deadline:
            status = "interrupted_time"
            break
        hypotheses_before = controller.snapshot() if hasattr(controller, "snapshot") else None
        try:
            action = controller.select_action(observation, deadline=deadline)
        except (NoSafePlanError, EmptyHypothesisError) as exc:
            status = "inconsistency" if isinstance(exc, NoSafePlanError) else "empty_hypothesis"
            error = str(exc)
            if log_path is not None:
                append_jsonl(
                    log_path,
                    {
                        "event": "controller_error",
                        "run_id": run_id,
                        "episode": episode_index,
                        "status": status,
                        "error": error,
                        "observation": observation_to_dict(observation),
                        "hypotheses": hypotheses_before,
                    },
                )
            break

        observation, reward, terminated, truncated, _info = env.step(action)
        return_sum += reward
        if action is Action.TOGGLE:
            toggles += 1
        try:
            changed = controller.update(observation)
        except EmptyHypothesisError as exc:
            status = "empty_hypothesis"
            if log_path is not None:
                append_jsonl(
                    log_path,
                    {
                        "event": "empty_hypothesis",
                        "run_id": run_id,
                        "episode": episode_index,
                        "error": str(exc),
                        "observation": observation_to_dict(observation),
                    },
                )
            break
        belief_changed = bool(belief_changed or changed)
        hypotheses_after = controller.snapshot() if hasattr(controller, "snapshot") else None
        meta = _controller_meta(controller)
        if meta.get("plan_kind"):
            plan_kinds.append(str(meta["plan_kind"]))
        if meta.get("plan_kind") == "probe":
            probe_steps += 1
        elif meta.get("plan_kind") == "task":
            task_steps += 1
        if meta.get("optional_reprobe"):
            optional_reprobe = True
        if meta.get("plan_kind") == "probe" and meta.get("target") is not None:
            target = int(meta["target"])
            if first_probe_target is None:
                first_probe_target = target
            if not probe_targets or probe_targets[-1] != target:
                probe_targets.append(target)
        if log_path is not None and log_every_step:
            append_jsonl(
                log_path,
                {
                    "event": "step",
                    "run_id": run_id,
                    "episode": episode_index,
                    "step": observation.step_index,
                    "action": action_name(action),
                    "reward": reward,
                    "terminated": terminated,
                    "truncated": truncated,
                    "observation": observation_to_dict(observation),
                    "hypotheses_before": meta.get("hypotheses_before", hypotheses_before),
                    "hypotheses_after": hypotheses_after,
                    "plan_kind": meta.get("plan_kind"),
                    "target": meta.get("target"),
                    "score": meta.get("score"),
                    "optional_reprobe": meta.get("optional_reprobe"),
                },
            )
        if render and on_render:
            on_render(
                render_ansi(
                    observation,
                    title=(
                        f"{run_id} step {observation.step_index} "
                        f"{action.value} kind={meta.get('plan_kind')}"
                    ),
                )
            )
            if isinstance(controller, ModelBasedAgent):
                on_render(
                    "hypotheses: "
                    + ", ".join(
                        f"{door}={list(controller.belief.names(door))}"
                        for door in controller.belief.door_ids
                    )
                )
        if terminated or truncated:
            status = "completed"
            break

    identified_after = None
    hypothesis_count = None
    if isinstance(controller, ModelBasedAgent):
        identified_after = {
            door_id: controller.belief.identified_name(door_id)
            for door_id in controller.belief.door_ids
        }
        hypothesis_count = controller.belief.total_hypothesis_count()
        belief_changed = belief_changed or (identified_before != identified_after)

    success = bool(terminated) and status == "completed"
    return {
        "index": episode_index,
        "status": status,
        "success": success,
        "terminated": terminated,
        "truncated": truncated,
        "steps": observation.step_index,
        "return_sum": return_sum,
        "toggles": toggles,
        "final_hypothesis_count": hypothesis_count,
        "identified": identified_after,
        "belief_changed": belief_changed,
        "planner_expansions": getattr(controller, "last_expansions", 0) - expansions_before,
        "wall_seconds": time.perf_counter() - started,
        "plan_kinds": plan_kinds,
        "probe_targets": probe_targets,
        "first_probe_target": first_probe_target,
        "probe_steps": probe_steps,
        "task_steps": task_steps,
        "optional_reprobe": optional_reprobe,
        "extra_probe_actions": int(getattr(controller, "extra_probe_actions", 0) or 0),
        "extra_probe_target": getattr(controller, "extra_probe_target", None),
        "extra_probe_log": copy.deepcopy(getattr(controller, "extra_probe_log", None)),
        "stopping_log": _episode_stopping_log(controller),
        "used_task_plan": "task" in plan_kinds,
        "supported_successful_plan": bool(success and ("task" in plan_kinds or not isinstance(controller, ModelBasedAgent))),
    }


def perm_label(perm: tuple[int, ...]) -> str:
    return ",".join(str(i) for i in perm)


def problem_id(layout_name: str, requested_rule: str, perm: tuple[int, ...]) -> str:
    return f"{layout_name}|{requested_rule}|perm{perm_label(perm)}"


def physical_problem_id(layout_name: str, requested_rule: str) -> str:
    return f"{layout_name}|{requested_rule}"


def iter_schedule(config: dict[str, Any]) -> list[tuple[str, str, tuple[int, ...], int, str]]:
    layout_names = list(config.get("layouts") or [config["layout"]])
    raw_perms = config.get("switch_permutations") or [[0, 1]]
    perms = [tuple(int(i) for i in perm) for perm in raw_perms]
    return [
        (layout_name, rule_name, perm, int(seed), method)
        for layout_name in layout_names
        for rule_name in config["rules"]
        for perm in perms
        for seed in config["seeds"]
        for method in config["methods"]
    ]


def run_method(
    *,
    layout: Layout,
    method: str,
    rule_name: str,
    seed: int,
    episodes: int,
    max_steps: int,
    expansion_cap: int,
    log_path: Path,
    render: bool,
    log_every_step: bool,
    deadline: float | None,
    on_render: Callable[[str], None] | None = None,
    layout_name: str | None = None,
    requested_rule: str | None = None,
    permutation: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    geometry = layout_name or layout.geometry
    requested = requested_rule or rule_name
    perm = permutation if permutation is not None else layout.switch_permutation
    run_id = f"{method}|{problem_id(geometry, requested, perm)}|seed{seed}"
    started = time.perf_counter()
    env = _make_env(layout, rule_name, max_steps)
    controller = _make_controller(method, layout, env, seed, expansion_cap)
    append_jsonl(
        log_path,
        {
            "event": "run_start",
            "run_id": run_id,
            "method": method,
            "layout": geometry,
            "requested_rule": requested,
            "rule": rule_name,
            "permutation": list(perm),
            "problem_id": problem_id(geometry, requested, perm),
            "physical_problem_id": physical_problem_id(geometry, requested),
            "seed": seed,
            "episodes": episodes,
            "evaluator_only_true_rule": rule_name,
        },
    )
    episode_records: list[dict[str, Any]] = []
    status = "completed"
    error = None
    try:
        for episode_index in range(episodes):
            if deadline is not None and time.perf_counter() >= deadline:
                status = "interrupted_time"
                break
            record = run_episode(
                env,
                controller,
                run_id=run_id,
                episode_index=episode_index,
                log_path=log_path,
                render=render,
                log_every_step=log_every_step,
                deadline=deadline,
                on_render=on_render,
            )
            episode_records.append(record)
            if record["status"] != "completed":
                status = record["status"]
                break
    except Exception as exc:  # noqa: BLE001 — record and continue the batch
        status = "exception"
        error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        append_jsonl(
            log_path,
            {
                "event": "exception",
                "run_id": run_id,
                "error": error,
            },
        )

    true_rule = hidden_rule_names(env)[0]
    identified = False
    belief_changed = any(ep.get("belief_changed") for ep in episode_records)
    if isinstance(controller, ModelBasedAgent):
        identified = controller.belief.identified_name(layout.door_ids[0]) == true_rule
    used_task_plan = any(ep.get("used_task_plan") for ep in episode_records)
    result = {
        "run_id": run_id,
        "method": method,
        "layout": geometry,
        "requested_rule": requested,
        "rule": rule_name,
        "permutation": list(perm),
        "problem_id": problem_id(geometry, requested, perm),
        "physical_problem_id": physical_problem_id(geometry, requested),
        "seed": seed,
        "status": status,
        "error": error,
        "episodes": episode_records,
        "belief_changed": belief_changed,
        "exact_rule_recovery": identified if method != "oracle" else True,
        "solved_after_learning": used_task_plan,
        "planner_expansions": getattr(controller, "last_expansions", 0),
        "wall_seconds": time.perf_counter() - started,
        "interactions": sum(ep.get("steps", 0) for ep in episode_records),
    }
    append_jsonl(log_path, {"event": "run_end", **{k: v for k, v in result.items() if k != "episodes"}})
    return result


def run_random_informative_audit(expansion_cap: int, n_seeds: int = 100) -> dict[str, Any]:
    """Fixed-belief audit used by the closed-door batch. Not a learner input."""
    layout = probe_spur_layout()
    belief = Belief.prior(layout.n_switches, layout.door_ids)
    belief.update(0, (False,))
    audit = audit_random_informative_selection(layout, belief, n_seeds, expansion_cap)
    audit["layout"] = layout.geometry
    audit["start_pos"] = list(layout.start)
    audit["start_bits"] = 0
    audit["fixed_evidence"] = {"0": [False]}
    return audit


def build_manifest(config: dict[str, Any], output_dir: Path, status: str) -> dict[str, Any]:
    return {
        "utc_time": datetime.now(timezone.utc).isoformat(),
        "git": _git_status(),
        "dependencies": _dependency_versions(),
        "hardware": hardware_summary(),
        "config": config,
        "output_dir": str(output_dir),
        "status": status,
        "max_wall_seconds": config.get("max_wall_seconds"),
        "note": (
            "True rule names appear only in evaluator run headers, never in learner observations."
        ),
    }


def run_benchmark(
    config: dict[str, Any],
    *,
    output_dir: Path | None = None,
    max_wall_seconds: float | None = None,
    render: bool | None = None,
    on_render: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir or config.get("output") or "results/pilot")
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "events.jsonl"
    if log_path.exists():
        log_path.unlink()
    wall = float(
        max_wall_seconds
        if max_wall_seconds is not None
        else config.get("max_wall_seconds", 120)
    )
    render = config.get("render", False) if render is None else render
    deadline = time.perf_counter() + wall
    started = time.perf_counter()
    manifest = build_manifest(config, output, "running")
    write_json(output / "manifest.json", manifest)

    audit_payload: dict[str, Any] | None = None
    if config.get("audit_random_informative"):
        audit_payload = run_random_informative_audit(int(config["planner_expansion_cap"]))
        write_json(output / "random_informative_audit.json", audit_payload)
        manifest["random_informative_audit"] = {
            "n_seeds": audit_payload["n_seeds"],
            "candidate_set": audit_payload["candidate_set"],
            "counts": audit_payload["counts"],
            "scores_all_equal": audit_payload["scores_all_equal"],
            "sampling": audit_payload["sampling"],
            "note": audit_payload["note"],
        }
        write_json(output / "manifest.json", manifest)

    schedule = iter_schedule(config)
    runs: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    interrupted = False
    for layout_name, requested_rule, perm, seed, method in schedule:
        now = time.perf_counter()
        if now >= deadline:
            interrupted = True
            remaining.append(
                {
                    "method": method,
                    "layout": layout_name,
                    "requested_rule": requested_rule,
                    "rule": requested_rule,
                    "permutation": list(perm),
                    "problem_id": problem_id(layout_name, requested_rule, perm),
                    "physical_problem_id": physical_problem_id(layout_name, requested_rule),
                    "seed": seed,
                    "status": "interrupted_time",
                    "episodes": [],
                }
            )
            continue
        base_layout = get_layout(layout_name)
        layout = with_switch_permutation(base_layout, perm)
        applied_rule = permute_rule_name(requested_rule, layout.n_switches, perm)
        result = run_method(
            layout=layout,
            method=method,
            rule_name=applied_rule,
            seed=seed,
            episodes=int(config["episodes_per_run"]),
            max_steps=int(config["max_episode_steps"]),
            expansion_cap=int(config["planner_expansion_cap"]),
            log_path=log_path,
            render=bool(render),
            log_every_step=bool(config.get("log_every_step", True)),
            deadline=deadline,
            on_render=on_render,
            layout_name=layout_name,
            requested_rule=requested_rule,
            permutation=perm,
        )
        runs.append(result)
        if result["status"] == "interrupted_time":
            interrupted = True

    runs.extend(remaining)
    elapsed = time.perf_counter() - started
    max_steps = int(config["max_episode_steps"])
    summary: dict[str, Any] = {
        "status": "interrupted_time" if interrupted else "completed",
        "wall_seconds": elapsed,
        "max_wall_seconds": wall,
        "completed_runs": sum(1 for run in runs if run.get("status") == "completed"),
        "total_scheduled_runs": len(schedule),
        "hardware": hardware_summary(),
        "metrics": summarize_runs(runs, max_steps),
        "runs": runs,
    }
    if audit_payload is not None:
        summary["random_informative_audit"] = {
            "n_seeds": audit_payload["n_seeds"],
            "candidate_set": audit_payload["candidate_set"],
            "counts": audit_payload["counts"],
            "scores_all_equal": audit_payload["scores_all_equal"],
            "sampling": audit_payload["sampling"],
            "note": audit_payload["note"],
        }
    prefixes = config.get("prefixes")
    if prefixes:
        summary["reprobe_report"] = write_reprobe_report(
            summary,
            output,
            max_steps,
            tuple(int(k) for k in prefixes),
        )
    write_json(output / "summary.json", summary)
    write_diagnostic_report(summary, output, max_steps)
    manifest["status"] = summary["status"]
    manifest["wall_seconds"] = elapsed
    write_json(output / "manifest.json", manifest)
    return summary
