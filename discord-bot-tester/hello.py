"""
discord-bot-tester Hello World
发送 "Test Hello World" 给你的 bot，等待并打印 bot 的回复。
"""

import asyncio
import sys
from datetime import datetime

import yaml
from discord import Client, Intents, Message


def load_config(path="config.yaml"):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    dc = cfg["discord"]
    return dc["token"], dc["bot"]


async def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    token, bot_name = load_config(config_path)

    # 启用所有 intents
    intents = Intents.all()
    client = Client(intents=intents)

    # -- 收集 bot 的所有响应事件 --
    log = []
    bot_user = None

    @client.event
    async def on_ready():
        nonlocal bot_user
        print(f"Logged in as {client.user}")
        
        # 找到目标 bot
        for guild in client.guilds:
            for member in guild.members:
                if member.name == bot_name and member.bot:
                    bot_user = member
                    print(f"Found bot: {bot_user.name} in {guild.name}")
                    return
        
        print(f"Warning: Could not find bot '{bot_name}'. Will match by name only.")

    @client.event
    async def on_message(message: Message):
        # 只监听目标 bot 的消息
        if message.author.name == bot_name:
            ts = datetime.now().isoformat(timespec="milliseconds")
            log.append(("NEW", message.id, message.content, ts))
            print(f"  [{ts}] NEW  id={message.id}  {message.content[:120]}")

    @client.event
    async def on_message_edit(before, after):
        # 监听 bot 的消息编辑
        if after.author.name == bot_name:
            ts = datetime.now().isoformat(timespec="milliseconds")
            log.append(("EDIT", after.id, after.content, ts))
            print(f"  [{ts}] EDIT id={after.id}  {after.content[:120]}")

    @client.event
    async def on_message_delete(message: Message):
        # 监听消息删除
        if message.author.name == bot_name:
            ts = datetime.now().isoformat(timespec="milliseconds")
            log.append(("DEL", message.id, None, ts))
            print(f"  [{ts}] DEL  id={message.id}")

    # -- 连接并发送 --
    await client.start(token)

    # 等待 ready 事件
    await asyncio.sleep(2)

    # 找到目标频道
    target_channel = None
    for guild in client.guilds:
        for channel in guild.text_channels:
            target_channel = channel
            print(f"Using channel: #{channel.name} in {guild.name}")
            break
        if target_channel:
            break

    if not target_channel:
        print("Error: No text channels found!")
        await client.close()
        return

    # 发送消息
    message = "Test Hello World"
    print(f"\n>>> {message}")
    await target_channel.send(message)

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

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())