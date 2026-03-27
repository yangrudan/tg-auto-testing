#!/usr/bin/env python3
"""
YAML-driven log validator for octos / e2e logs.

Usage:
  python run_yaml_log_check.py path/to/scenario.yaml [--log-file /path/to/bot_events.log]

Scenario file supports steps like:

steps:
  - wait_for_test_trigger:
      tc_id: TC-FM-02
      correlation_id: run-20260326-001
      timeout: 30
  - expect_event:
      event: test_trigger
      payload:
        tc_id: TC-FM-02
        correlation_id: run-20260326-001

This script reuses the parsing helpers in e2e_log.py to find JSON-lines events.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

# reuse helpers from e2e_log.py
from e2e_log import iter_log_json_lines, find_test_trigger


def find_event(path: str, event_type: str, payload_pattern: Dict[str, Any]):
    """Find a log entry whose 'event' == event_type and whose payload contains payload_pattern keys with equal values."""
    for entry in iter_log_json_lines(path):
        if entry.get("event") != event_type:
            continue
        payload = entry.get("payload", {})
        ok = True
        for k, v in (payload_pattern or {}).items():
            if payload.get(k) != v:
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
    data = yaml.safe_load(Path(path).read_text())
    steps = data.get("steps", [])
    ok = True

    print(f"Scenario: {data.get('name', path)}")
    print(f"Using log file: {log_file}")

    for i, step in enumerate(steps):
        print(f"Step {i+1}: {step}")
        if "wait_for_test_trigger" in step:
            #!/usr/bin/env python3
            """
            YAML-driven log validator for octos / e2e logs.

            Usage:
              python run_yaml_log_check.py path/to/scenario.yaml [--log-file /path/to/bot_events.log]

            Scenario file supports steps like:

            steps:
              - wait_for_test_trigger:
                  tc_id: TC-FM-02
                  correlation_id: run-20260326-001
                  timeout: 30
              - expect_event:
                  event: test_trigger
                  payload:
                    tc_id: TC-FM-02
                    correlation_id: run-20260326-001

            This script reuses the parsing helpers in e2e_log.py to find JSON-lines events.
            """

            import argparse
            import sys
            import time
            from pathlib import Path
            from typing import Any, Dict

            import yaml

            # reuse helpers from e2e_log.py
            from e2e_log import iter_log_json_lines, find_test_trigger


            def find_event(path: str, event_type: str, payload_pattern: Dict[str, Any]):
                """Find a log entry whose 'event' == event_type and whose payload contains payload_pattern keys with equal values."""
                for entry in iter_log_json_lines(path):
                    if entry.get("event") != event_type:
                        continue
                    payload = entry.get("payload", {})
                    ok = True
                    for k, v in (payload_pattern or {}).items():
                        if payload.get(k) != v:
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
