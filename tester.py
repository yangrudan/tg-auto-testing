"""
crew-tg-tester — YAML-driven Telegram bot test runner.

Reads a YAML scenario file, sends messages/files to a bot as a real
Telegram user, captures the full response lifecycle (new/edit/delete),
runs assertions, and writes timeline.jsonl + report.md.
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError


# ---------------------------------------------------------------------------
# Config & scenario loading
# ---------------------------------------------------------------------------

def load_config(path="config.yaml"):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    tg = cfg["telegram"]
    return {
        "api_id": tg["api_id"],
        "api_hash": tg["api_hash"],
        "session_file": tg.get("session_file", "crew_tester"),
        "bot": tg.get("bot"),
    }


def load_scenario(path):
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Event:
    ts: str
    event_type: str          # "new", "edit", "delete"
    message_id: int
    text: str | None = None

    def to_dict(self):
        return {
            "ts": self.ts,
            "type": self.event_type,
            "msg_id": self.message_id,
            "text": self.text,
        }


@dataclass
class StepResult:
    index: int
    tag: str | None = None
    sent: str | None = None
    sent_file: str | None = None
    reply: str | None = None
    result: str = "PASS"     # PASS / FAIL / TIMEOUT / SKIP
    detail: str | None = None
    events: list[Event] = field(default_factory=list)
    elapsed: float = 0
    children: list["StepResult"] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Event collector
# ---------------------------------------------------------------------------

class EventCollector:
    """Collects Telethon events for the current step."""

    def __init__(self):
        self._events: list[Event] = []
        self._event_count_at_step_start = 0

    def start_step(self):
        self._event_count_at_step_start = len(self._events)

    @property
    def step_event_count(self):
        return len(self._events) - self._event_count_at_step_start

    def step_events(self) -> list[Event]:
        return self._events[self._event_count_at_step_start:]

    def add(self, event_type: str, message_id: int, text: str | None):
        ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        ev = Event(ts=ts, event_type=event_type, message_id=message_id, text=text)
        self._events.append(ev)
        # live output
        label = event_type.upper().ljust(4)
        preview = (text or "")[:120]
        print(f"  [{ts}] {label} id={message_id}  {preview}")

    def final_reply(self) -> str | None:
        """Compute final reply text from step events (excluding deleted msgs)."""
        step_evs = self.step_events()
        deleted_ids = {e.message_id for e in step_evs if e.event_type == "delete"}
        latest: dict[int, str] = {}
        for e in step_evs:
            if e.event_type in ("new", "edit") and e.message_id not in deleted_ids:
                latest[e.message_id] = e.text or ""
        if not latest:
            return None
        return "\n".join(latest.values())


def register_handlers(client, collector: EventCollector, bot_username: str):
    @client.on(events.NewMessage(from_users=bot_username))
    async def on_new(event):
        collector.add("new", event.id, event.text)

    @client.on(events.MessageEdited(from_users=bot_username))
    async def on_edit(event):
        collector.add("edit", event.id, event.text)

    @client.on(events.MessageDeleted())
    async def on_delete(event):
        for mid in event.deleted_ids:
            collector.add("delete", mid, None)


# ---------------------------------------------------------------------------
# Settle detection
# ---------------------------------------------------------------------------

async def wait_settle(collector: EventCollector, settle_timeout: int, max_wait: int):
    """Wait until bot stops producing events. Returns (elapsed, timed_out)."""
    elapsed = 0
    last_count = collector.step_event_count
    quiet = 0

    while elapsed < max_wait:
        await asyncio.sleep(1)
        elapsed += 1

        current = collector.step_event_count
        if current > last_count:
            last_count = current
            quiet = 0
        else:
            quiet += 1

        if quiet >= settle_timeout and collector.step_event_count > 0:
            return elapsed, False

    return elapsed, collector.step_event_count == 0  # timeout if no events at all


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------

async def send_message(client, bot: str, step: dict, scenario_dir: str):
    """Send text and/or file. Returns description of what was sent."""
    text = step.get("send")
    file_path = step.get("send_file")

    if file_path:
        full_path = os.path.join(scenario_dir, file_path)
        caption = text or ""
        print(f"\n>>> [file] {file_path}" + (f"  caption: {caption}" if caption else ""))
        try:
            await client.send_file(bot, full_path, caption=caption)
        except FloodWaitError as e:
            print(f"  ⏳ FloodWait: sleeping {e.seconds}s ...")
            await asyncio.sleep(e.seconds)
            await client.send_file(bot, full_path, caption=caption)
        return f"[file:{file_path}] {caption}".strip()
    elif text:
        print(f"\n>>> {text}")
        try:
            await client.send_message(bot, text)
        except FloodWaitError as e:
            print(f"  ⏳ FloodWait: sleeping {e.seconds}s ...")
            await asyncio.sleep(e.seconds)
            await client.send_message(bot, text)
        return text
    return None


def run_assertions(step: dict, reply: str | None) -> tuple[str, str | None]:
    """Run expect_contains / expect_not_contains. Returns (result, detail)."""
    if reply is None:
        if "expect_contains" in step or "expect_not_contains" in step:
            return "FAIL", "No reply from bot"
        return "PASS", None

    expect = step.get("expect_contains")
    if expect and expect not in reply:
        return "FAIL", f"Expected '{expect}' not found in reply"

    not_expect = step.get("expect_not_contains")
    if not_expect and not_expect in reply:
        return "FAIL", f"Unexpected '{not_expect}' found in reply"

    return "PASS", None


async def run_step(
    client,
    step: dict,
    step_index: int,
    collector: EventCollector,
    defaults: dict,
    bot: str,
    scenario_dir: str,
) -> StepResult:
    """Execute a single step: send → settle → assert → branch."""
    collector.start_step()

    tag = step.get("tag")
    settle_timeout = step.get("settle_timeout", defaults.get("settle_timeout", 5))
    max_wait = step.get("max_wait", defaults.get("max_wait", 120))

    # Send
    sent = await send_message(client, bot, step, scenario_dir)
    sent_file = step.get("send_file")

    # If nothing to send (pure tag/assertion step with no send), skip settle
    if sent is None:
        result = StepResult(
            index=step_index,
            tag=tag,
            result="SKIP" if not tag else "PASS",
            detail="No send action",
        )
        print(f"  [{tag or step_index}] SKIP (no send action)")
        return result

    # Settle
    elapsed, timed_out = await wait_settle(collector, settle_timeout, max_wait)
    reply = collector.final_reply()
    step_events = list(collector.step_events())

    # Assertions
    if timed_out and reply is None:
        result_str, detail = "TIMEOUT", "No reply within max_wait"
    else:
        result_str, detail = run_assertions(step, reply)

    sr = StepResult(
        index=step_index,
        tag=tag,
        sent=sent,
        sent_file=sent_file,
        reply=reply,
        result=result_str,
        detail=detail,
        events=step_events,
        elapsed=elapsed,
    )

    status = "✅" if result_str == "PASS" else "❌" if result_str == "FAIL" else "⏰"
    print(f"  [{tag or step_index}] {status} {result_str}" + (f" — {detail}" if detail else ""))

    # Conditional branching
    on_response = step.get("on_response")
    if on_response and reply:
        matched = False
        for branch in on_response:
            if "contains" in branch and branch["contains"] in reply:
                matched = True
                for i, sub_step in enumerate(branch.get("steps", [])):
                    child = await run_step(
                        client, sub_step, f"{step_index}.{i}",
                        collector, defaults, bot, scenario_dir,
                    )
                    sr.children.append(child)
                break
        if not matched:
            for branch in on_response:
                if "default" in branch:
                    for i, sub_step in enumerate(branch["default"].get("steps", [])):
                        child = await run_step(
                            client, sub_step, f"{step_index}.{i}",
                            collector, defaults, bot, scenario_dir,
                        )
                        sr.children.append(child)
                    break

    return sr


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------

async def run_scenario(client, scenario: dict, config: dict, scenario_path: str):
    bot = scenario.get("bot", config["bot"])
    if not bot:
        print("Error: no bot specified in scenario or config.")
        sys.exit(1)

    defaults = scenario.get("defaults", {})
    steps = scenario.get("steps", [])
    scenario_dir = os.path.dirname(os.path.abspath(scenario_path))

    collector = EventCollector()
    register_handlers(client, collector, bot)

    print(f"Running scenario: {scenario.get('name', scenario_path)}")
    print(f"Bot: {bot}  |  Steps: {len(steps)}")
    print(f"{'='*60}")

    results = []
    for i, step in enumerate(steps):
        sr = await run_step(client, step, i, collector, defaults, bot, scenario_dir)
        results.append(sr)

    return results


# ---------------------------------------------------------------------------
# Output: timeline.jsonl + report.md
# ---------------------------------------------------------------------------

def flatten_results(results: list[StepResult]) -> list[StepResult]:
    """Flatten results including children for reporting."""
    flat = []
    for r in results:
        flat.append(r)
        if r.children:
            flat.extend(flatten_results(r.children))
    return flat


def write_timeline(results: list[StepResult], output_dir: str):
    path = os.path.join(output_dir, "timeline.jsonl")
    with open(path, "w") as f:
        for r in flatten_results(results):
            # outbound
            if r.sent:
                f.write(json.dumps({
                    "ts": r.events[0].ts if r.events else "",
                    "dir": "out",
                    "type": "send",
                    "text": r.sent,
                    "step": r.index,
                    "tag": r.tag,
                }, ensure_ascii=False) + "\n")
            # inbound events
            for ev in r.events:
                f.write(json.dumps({
                    "ts": ev.ts,
                    "dir": "in",
                    **ev.to_dict(),
                }, ensure_ascii=False) + "\n")
            # result
            f.write(json.dumps({
                "ts": r.events[-1].ts if r.events else "",
                "dir": "sys",
                "type": "result",
                "step": r.index,
                "tag": r.tag,
                "result": r.result,
                "detail": r.detail,
            }, ensure_ascii=False) + "\n")
    print(f"  Timeline: {path}")


def write_report(scenario: dict, scenario_path: str, results: list[StepResult], output_dir: str):
    path = os.path.join(output_dir, "report.md")
    flat = flatten_results(results)

    counts = {"PASS": 0, "FAIL": 0, "TIMEOUT": 0, "SKIP": 0}
    for r in flat:
        counts[r.result] = counts.get(r.result, 0) + 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    name = scenario.get("name", scenario_path)
    bot = scenario.get("bot", "")

    lines = [
        f"# Test Report: {name}",
        f"- Date: {now}",
        f"- Bot: {bot}",
        f"- Scenario: {scenario_path}",
        "",
        "## Summary",
        "| Total | PASS | FAIL | TIMEOUT | SKIP |",
        "|-------|------|------|---------|------|",
        f"| {len(flat)} | {counts['PASS']} | {counts['FAIL']} | {counts['TIMEOUT']} | {counts['SKIP']} |",
        "",
        "## Details",
        "| # | Tag | Sent | Expected | Reply (truncated) | Result |",
        "|---|-----|------|----------|-------------------|--------|",
    ]

    for r in flat:
        sent = (r.sent or "—")[:40]
        expect = ""
        # reconstruct expected from original step (not stored, use detail)
        reply = (r.reply or "—")[:60].replace("\n", " ")
        result_icon = {"PASS": "PASS", "FAIL": "**FAIL**", "TIMEOUT": "TIMEOUT", "SKIP": "SKIP"}.get(r.result, r.result)
        detail_str = f" ({r.detail})" if r.detail else ""
        lines.append(f"| {r.index} | {r.tag or '—'} | {sent} | | {reply} | {result_icon}{detail_str} |")

    lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Report:   {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    # Parse args
    if len(sys.argv) < 2:
        print("Usage: python tester.py <scenario.yaml|scenarios_dir/> [-o output_dir] [-c config.yaml]")
        sys.exit(1)

    scenario_arg = sys.argv[1]
    output_base = "output"
    config_path = "config.yaml"

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "-o" and i + 1 < len(args):
            output_base = args[i + 1]
            i += 2
        elif args[i] == "-c" and i + 1 < len(args):
            config_path = args[i + 1]
            i += 2
        else:
            i += 1

    config = load_config(config_path)

    # Collect scenario files
    if os.path.isdir(scenario_arg):
        scenario_files = sorted(Path(scenario_arg).glob("*.yaml"))
        if not scenario_files:
            print(f"No .yaml files found in {scenario_arg}")
            sys.exit(1)
    else:
        scenario_files = [Path(scenario_arg)]

    # Connect
    client = TelegramClient(config["session_file"], config["api_id"], config["api_hash"])
    await client.start()
    print("Logged in.\n")

    for sf in scenario_files:
        scenario = load_scenario(sf)

        # Create output dir
        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        scenario_name = scenario.get("name", sf.stem).replace(" ", "_")
        output_dir = os.path.join(output_base, f"{ts}_{scenario_name}")
        os.makedirs(output_dir, exist_ok=True)

        results = await run_scenario(client, scenario, config, str(sf))

        # Summary
        flat = flatten_results(results)
        total = len(flat)
        passed = sum(1 for r in flat if r.result == "PASS")
        failed = sum(1 for r in flat if r.result == "FAIL")
        timed_out = sum(1 for r in flat if r.result == "TIMEOUT")

        print(f"\n{'='*60}")
        print(f"Scenario: {scenario.get('name', sf.name)}")
        print(f"Results:  {passed} PASS / {failed} FAIL / {timed_out} TIMEOUT / {total} total")
        print(f"{'='*60}")

        # Write outputs
        write_timeline(results, output_dir)
        write_report(scenario, str(sf), results, output_dir)
        print()

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
