"""
crew-tg-tester Hello World
发送 "Test Hello World" 给你的 bot，等待并打印 bot 的回复。
"""

import asyncio
import sys
from datetime import datetime, timezone

import yaml
from telethon import TelegramClient, events


def load_config(path="config.yaml"):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    tg = cfg["telegram"]
    return tg["api_id"], tg["api_hash"], tg["bot"]


async def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    api_id, api_hash, bot_username = load_config(config_path)

    client = TelegramClient("crew_tester", api_id, api_hash)

    # -- 收集 bot 的所有响应事件 --
    log = []

    @client.on(events.NewMessage(from_users=bot_username))
    async def on_new(event):
        ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        log.append(("NEW", event.id, event.text, ts))
        print(f"  [{ts}] NEW  id={event.id}  {event.text[:120]}")

    @client.on(events.MessageEdited(from_users=bot_username))
    async def on_edit(event):
        ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        log.append(("EDIT", event.id, event.text, ts))
        print(f"  [{ts}] EDIT id={event.id}  {event.text[:120]}")

    @client.on(events.MessageDeleted())
    async def on_delete(event):
        ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        for mid in event.deleted_ids:
            log.append(("DEL", mid, None, ts))
            print(f"  [{ts}] DEL  id={mid}")

    # -- 连接并发送 --
    await client.start()
    print(f"Logged in. Sending to {bot_username} ...")

    message = "Test Hello World"
    print(f"\n>>> {message}")
    await client.send_message(bot_username, message)

    # -- 等待 bot 回复稳定（settle detection）--
    settle_timeout = 10  # 秒：无新事件则判定完成
    max_wait = 60  # 秒：最大等待时间
    elapsed = 0
    last_event_count = 0

    quiet_seconds = 0
    while elapsed < max_wait:
        await asyncio.sleep(1)
        elapsed += 1

        if len(log) > last_event_count:
            # 有新事件，重置安静计时
            last_event_count = len(log)
            quiet_seconds = 0
        else:
            quiet_seconds += 1

        if quiet_seconds >= settle_timeout and len(log) > 0:
            break

    # -- 汇总结果 --
    print(f"\n{'='*60}")
    print(f"Done. Captured {len(log)} events in {elapsed}s.")
    print(f"{'='*60}")

    # 找到最终回复（未被删除的消息的最后版本）
    deleted_ids = {mid for typ, mid, _, _ in log if typ == "DEL"}
    final_texts = {}
    for typ, mid, text, ts in log:
        if typ in ("NEW", "EDIT") and mid not in deleted_ids:
            final_texts[mid] = text

    if final_texts:
        print("\nBot final reply:")
        for mid, text in final_texts.items():
            print(f"  [msg {mid}] {text}")
    else:
        print("\nNo reply received from bot.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
