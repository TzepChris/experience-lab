"""JSON helpers and incremental JSONL logging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from experience_lab.types import Action, Observation


def observation_to_dict(observation: Observation) -> dict[str, Any]:
    return {
        "agent_pos": list(observation.agent_pos),
        "goal_pos": list(observation.goal_pos),
        "switch_ids": list(observation.switch_ids),
        "door_ids": list(observation.door_ids),
        "switch_bits": list(observation.switch_bits),
        "door_open": list(observation.door_open),
        "step_index": observation.step_index,
        "static_grid": [list(row) for row in observation.static_grid],
        "switch_positions": [list(pos) for pos in observation.switch_positions],
        "door_positions": [list(pos) for pos in observation.door_positions],
    }


def action_name(action: Action | None) -> str | None:
    return None if action is None else action.value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")
        handle.flush()
