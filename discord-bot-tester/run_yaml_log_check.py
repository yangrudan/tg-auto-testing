#!/usr/bin/env python3
"""
Clean YAML-driven log validator for octos / e2e logs.

This script reads a scenario YAML and performs log-based assertions by
polling a JSON-lines log file produced by `octos_log.py`.

Supported step types:
  - wait_for_test_trigger: matches test_trigger events by tc_id/correlation_id
  - expect_event: matches an arbitrary event name and payload assertions
  - sleep: wait N seconds

Payload matching supports nested keys with dot notation and '*_contains' suffixes.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

from e2e_log import iter_log_json_lines, find_test_trigger


def get_nested(d: Dict[str, Any], key: str):
    parts = key.split(".")
    cur = d
    for p in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def find_event(path: str, event_type: str, payload_pattern: Dict[str, Any]):
    for entry in iter_log_json_lines(path):
        if entry.get("event") != event_type:
            continue
        payload = entry.get("payload", {}) or {}
        ok = True
        for k, v in (payload_pattern or {}).items():
            if k.endswith("_contains"):
                base = k[: -len("_contains")]
                val = get_nested(payload, base)
                if val is None or str(v) not in str(val):
                    ok = False
                    break
            else:
                val = get_nested(payload, k)
                if val != v:
                    ok = False
                    break
        if ok:
            return entry
    return None


def run_step_wait_for_test_trigger(step: dict, log_file: str) -> bool:
    params = step.get("wait_for_test_trigger") or {}
    tc = params.get("tc_id")
    corr = params.get("correlation_id")
    timeout = int(params.get("timeout", 30))
    poll_interval = float(params.get("poll_interval", 1.0))

    deadline = time.time() + timeout
    while time.time() < deadline:
        found = find_test_trigger(log_file, tc, corr)
        if found:
            print(f"Found test_trigger: tc_id={tc} correlation_id={corr}")
            return True
        time.sleep(poll_interval)

    print(f"Timeout waiting for test_trigger tc_id={tc} correlation_id={corr} in {log_file}")
    return False


def run_step_expect_event(step: dict, log_file: str) -> bool:
    params = step.get("expect_event") or {}
    event = params.get("event")
    payload = params.get("payload", {})
    timeout = int(params.get("timeout", 30))
    poll_interval = float(params.get("poll_interval", 1.0))

    deadline = time.time() + timeout
    while time.time() < deadline:
        found = find_event(log_file, event, payload)
        if found:
            print(f"Found event '{event}' matching payload {payload}")
            return True
        time.sleep(poll_interval)

    print(f"Timeout waiting for event '{event}' matching {payload} in {log_file}")
    return False


def run_scenario(path: str, log_file: str) -> int:
    text = Path(path).read_text()
    data = yaml.safe_load(text)
    if data is None:
        print(f"Failed to parse YAML scenario or file is empty: {path}")
        return 1

    steps = data.get("steps", [])
    ok = True

    print(f"Scenario: {data.get('name', path)}")
    print(f"Using log file: {log_file}")

    for i, step in enumerate(steps):
        print(f"Step {i+1}: {step}")
        if "wait_for_test_trigger" in step:
            res = run_step_wait_for_test_trigger(step, log_file)
        elif "expect_event" in step:
            res = run_step_expect_event(step, log_file)
        elif "sleep" in step:
            t = float(step.get("sleep", 1))
            print(f"Sleeping {t}s")
            time.sleep(t)
            res = True
        else:
            print(f"Unknown step type: {step}. Skipping")
            res = True

        if not res:
            print(f"Step {i+1} FAILED")
            ok = False
        else:
            print(f"Step {i+1} OK")

    return 0 if ok else 2


def main():
    ap = argparse.ArgumentParser(description="Run YAML-driven log checks against octos / bot_events.log")
    ap.add_argument("scenario", help="YAML scenario file")
    ap.add_argument("--log-file", help="path to bot events log (jsonl)", default="bot_events.log")
    args = ap.parse_args()

    scenario_path = args.scenario
    log_file = args.log_file

    if not Path(scenario_path).exists():
        print(f"Scenario file not found: {scenario_path}")
        sys.exit(1)

    if not Path(log_file).exists():
        print(f"Log file not found (will still poll until created): {log_file}")

    rc = run_scenario(scenario_path, log_file)
    sys.exit(rc)


if __name__ == "__main__":
    main()
