"""Validate cumulative Codex 0.154.0 session usage before deriving turn deltas."""
import hashlib
import json
from pathlib import Path

FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens")
SUPPORTED_VERSION = "0.154.0"


class UsageUnavailable(ValueError):
    pass


def counters(value):
    if not isinstance(value, dict) or any(type(value.get(key)) is not int or value[key] < 0 for key in FIELDS):
        raise UsageUnavailable("missing_or_invalid_counters")
    result = {key: value[key] for key in FIELDS}
    if result["cached_input_tokens"] > result["input_tokens"]:
        raise UsageUnavailable("cached_input_exceeds_input")
    if "total_tokens" in value and value["total_tokens"] != result["input_tokens"] + result["output_tokens"]:
        raise UsageUnavailable("inconsistent_total_tokens")
    return result


def read_session(agent_dir, session_id):
    paths = sorted((Path(agent_dir) / "sessions").rglob("*.jsonl"))
    if len(paths) != 1:
        raise UsageUnavailable("missing_or_ambiguous_native_session")
    path = paths[0]
    content = path.read_bytes()
    try:
        events = [json.loads(line) for line in content.decode("utf-8").splitlines() if line.strip()]
    except (ValueError, UnicodeError) as exc:
        raise UsageUnavailable("malformed_native_session") from exc
    if any(not isinstance(event, dict) for event in events):
        raise UsageUnavailable("malformed_native_session")
    metadata = [event.get("payload") for event in events if event.get("type") == "session_meta"]
    if len(metadata) != 1 or not isinstance(metadata[0], dict) or metadata[0].get("id") != session_id:
        raise UsageUnavailable("native_session_identity_mismatch")
    if metadata[0].get("cli_version") != SUPPORTED_VERSION:
        raise UsageUnavailable("unverified_native_cli_version")
    records = []
    previous = {key: 0 for key in FIELDS}
    for event in events:
        payload = event.get("payload") or {}
        if event.get("type") != "event_msg" or not isinstance(payload, dict) or payload.get("type") != "token_count":
            continue
        info = payload.get("info")
        if info is None:  # Codex also emits rate-limit-only token_count events.
            continue
        if not isinstance(info, dict):
            raise UsageUnavailable("malformed_token_count")
        total = counters(info.get("total_token_usage"))
        if any(total[key] < previous[key] for key in FIELDS):
            raise UsageUnavailable("native_counter_reset")
        records.append(event)
        previous = total
    if not records:
        raise UsageUnavailable("missing_native_token_counts")
    return records, previous, {"path": str(path), "sha256": hashlib.sha256(content).hexdigest(),
                               "token_count_records": len(records), "cli_version": metadata[0]["cli_version"]}


def reconcile_usage(steps, agent_dirs, expected_count):
    empty = {key: None for key in FIELDS}
    unavailable = {"status": "unavailable", "totals": empty, "turn_deltas": [], "evidence": []}
    try:
        if not steps or len(steps) != expected_count or len(agent_dirs) != len(steps):
            raise UsageUnavailable("incomplete_turn_sequence")
        ids = [step.get("session_id") for step in steps]
        if not all(ids) or len(set(ids)) != 1:
            raise UsageUnavailable("session_not_continuous")
        previous_records, previous = [], {key: 0 for key in FIELDS}
        deltas, evidence = [], []
        for step, agent_dir in zip(steps, agent_dirs):
            if step.get("status") != "completed":
                raise UsageUnavailable("turn_not_completed")
            records, total, proof = read_session(agent_dir, ids[0])
            if records[:len(previous_records)] != previous_records or len(records) <= len(previous_records):
                raise UsageUnavailable("native_history_not_extended")
            if counters(step.get("reported_usage")) != total:
                raise UsageUnavailable("cli_and_native_totals_disagree")
            delta = {key: total[key] - previous[key] for key in FIELDS}
            counters(delta)
            deltas.append(delta)
            evidence.append(proof)
            previous_records, previous = records, total
        return {"status": "verified_cumulative", "reason": None, "totals": previous,
                "turn_deltas": deltas, "evidence": evidence,
                "method": "same native session; token-count history prefix; monotone counters; CLI/native agreement; adjacent cumulative differences",
                "input_includes_cached": True, "cost_usd": None}
    except (UsageUnavailable, OSError) as exc:
        return {**unavailable, "reason": str(exc) if isinstance(exc, UsageUnavailable) else "native_session_unreadable"}
