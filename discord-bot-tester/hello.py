import asyncio
import sys
import yaml
from datetime import datetime, timezone
import discord

def load_config(path="config.yaml"):
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    dc = cfg["discord"]
    return dc["token"], int(dc["channel_id"]), int(dc["bot_user_id"])

async def main():
    token, channel_id, bot_user_id = load_config()

    log = []
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_message(msg):
        if msg.author.id == bot_user_id:
            ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            log.append(("NEW", msg.id, msg.content, ts))
            print(f"[{ts}] NEW {msg.id} | {msg.content[:100]}")

    @client.event
    async def on_message_edit(before, after):
        if after.author.id == bot_user_id:
            ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            log.append(("EDIT", after.id, after.content, ts))
            print(f"[{ts}] EDIT {after.id} | {after.content[:100]}")

    @client.event
    async def on_message_delete(msg):
        if msg.author.id == bot_user_id:
            ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            log.append(("DEL", msg.id, None, ts))
            print(f"[{ts}] DEL {msg.id}")

    @client.event
    async def on_ready():
        print(f"\n登录成功：{client.user}")
        channel = client.get_channel(channel_id)
        if channel:
            print(">>> Test Hello World")
            await channel.send("Test Hello World")

    async def wait_loop():
        await asyncio.sleep(15)
        await client.close()

    async with client:
        asyncio.create_task(wait_loop())
        await client.start(token)

    print("\n==== 结果 ====")
    deleted = {mid for t,mid,_,_ in log if t=="DEL"}
    for t,mid,text,_ in log:
        if t in ("NEW","EDIT") and mid not in deleted:
            print(f"机器人最终回复：{text}")

if __name__ == "__main__":
    asyncio.run(main())