"""
discord-bot-tester — YAML-driven Discord bot test runner.

Reads a YAML scenario file, sends messages to a bot as a real
Discord user, captures the full response lifecycle (new/edit/delete),
runs assertions, and writes timeline.jsonl + report.md.
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml
from discord import Client, Intents, Message
from discord.errors import Forbidden


# ---------------------------------------------------------------------------
# Config & scenario loading
# ---------------------------------------------------------------------------

def load_config(path="config.yaml"):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    dc = cfg["discord"]
    return {
        "token": dc["token"],
        "bot": dc.get("bot"),
        "guild_id": dc.get("guild_id"),
        "channel_name": dc.get("channel_name"),
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
    reply: str | None = None
    result: str = "PASS"     # PASS / FAIL / TIMEOUT / SKIP
    detail: str | None = None
    events: list = field(default_factory=list)
    elapsed: float = 0
    children: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Event collector
# ---------------------------------------------------------------------------

class EventCollector:
    """Collects Discord events for the current step."""

    def __init__(self):
        self._events = []
        self._event_count_at_step_start = 0

    def start_step(self):
        self._event_count_at_step_start = len(self._events)

    @property
    def step_event_count(self):
        return len(self._events) - self._event_count_at_step_start

    def step_events(self):
        return self._events[self._event_count_at_step_start:]

    def add(self, event_type: str, message_id: int, text: str | None):
        ts = datetime.now().isoformat(timespec="milliseconds")
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
        latest = {}
        for e in step_evs:
            if e.event_type in ("new", "edit") and e.message_id not in deleted_ids:
                latest[e.message_id] = e.text or ""
        if not latest:
            return None
        return "\n".join(latest.values())


class DiscordTester:
    def __init__(self, token: str, bot_name: str):
        intents = Intents.all()
        self.client = Client(intents=intents)
        self.token = token
        self.bot_name = bot_name
        self.collector = EventCollector()
        self.target_channel = None
        self._setup_handlers()

    def _setup_handlers(self):
        @self.client.event
        async def on_ready():
            print(f"Logged in as {self.client.user}")

        @self.client.event
        async def on_message(message: Message):
            # 只监听目标 bot 的消息
            if message.author.name == self.bot_name and not message.author.bot:
                return
            if message.author.name == self.bot_name:
                self.collector.add("new", message.id, message.content)

        @self.client.event
        async def on_message_edit(before, after):
            # 监听 bot 的消息编辑
            if after.author.name == self.bot_name:
                self.collector.add("edit", after.id, after.content)

        @self.client.event
        async def on_message_delete(message: Message):
            # 监听消息删除
            if message.author.name == self.bot_name:
                self.collector.add("delete", message.id, None)


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

async def send_message(channel, step: dict):
    """Send text message. Returns description of what was sent."""
    text = step.get("send")

    if text:
        print(f"\n>>> {text}")
        await channel.send(text)
        return text
    return None


def run_assertions(step: dict, reply: str | None) -> tuple:
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
    channel,
    step: dict,
    step_index: int,
    collector: EventCollector,
    defaults: dict,
) -> StepResult:
    """Execute a single step: send → settle → assert → branch."""
    collector.start_step()

    tag = step.get("tag")
    settle_timeout = step.get("settle_timeout", defaults.get("settle_timeout", 5))
    max_wait = step.get("max_wait", defaults.get("max_wait", 120))

    # Send
    sent = await send_message(channel, step)

    # If nothing to send, skip settle
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
                        channel, sub_step, f"{step_index}.{i}",
                        collector, defaults,
                    )
                    sr.children.append(child)
                break
        if not matched:
            for branch in on_response:
                if "default" in branch:
                    for i, sub_step in enumerate(branch["default"].get("steps", [])):
                        child = await run_step(
                            channel, sub_step, f"{step_index}.{i}",
                            collector, defaults,
                        )
                        sr.children.append(child)
                    break

    return sr


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------

async def run_scenario(tester: DiscordTester, scenario: dict, config: dict):
    bot = scenario.get("bot", config["bot"])
    if not bot:
        print("Error: no bot specified in scenario or config.")
        sys.exit(1)

    defaults = scenario.get("defaults", {})
    steps = scenario.get("steps", [])

    # 重置 collector
    tester.collector = EventCollector()

    print(f"Running scenario: {scenario.get('name', 'Unknown')}")
    print(f"Bot: {bot}  |  Steps: {len(steps)}")
    print(f"{'='*60}")

    results = []
    for i, step in enumerate(steps):
        sr = await run_step(
            tester.target_channel, step, i, tester.collector, defaults,
        )
        results.append(sr)

    return results


# ---------------------------------------------------------------------------
# Output: timeline.jsonl + report.md
# ---------------------------------------------------------------------------

def flatten_results(results: list) -> list:
    """Flatten results including children for reporting."""
    flat = []
    for r in results:
        flat.append(r)
        if r.children:
            flat.extend(flatten_results(r.children))
    return flat


def write_timeline(results: list, output_dir: str):
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


def write_report(scenario: dict, scenario_path: str, results: list, output_dir: str):
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

    # Create tester
    tester = DiscordTester(config["token"], config["bot"])

    # Connect
    await tester.client.start(config["token"])

    # 等待 ready
    await asyncio.sleep(2)

    # 找到目标频道
    target_channel = None
    for guild in tester.client.guilds:
        if config.get("guild_id") and guild.id != config["guild_id"]:
            continue
        for channel in guild.text_channels:
            if not config.get("channel_name") or channel.name == config["channel_name"]:
                target_channel = channel
                print(f"Using channel: #{channel.name} in {guild.name}")
                break
        if target_channel:
            break

    if not target_channel:
        print("Error: No target channel found!")
        await tester.client.close()
        sys.exit(1)

    tester.target_channel = target_channel

    for sf in scenario_files:
        scenario = load_scenario(sf)

        # Create output dir
        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        scenario_name = scenario.get("name", sf.stem).replace(" ", "_")
        output_dir = os.path.join(output_base, f"{ts}_{scenario_name}")
        os.makedirs(output_dir, exist_ok=True)

        results = await run_scenario(tester, scenario, config)

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

    await tester.client.close()


if __name__ == "__main__":
    asyncio.run(main())