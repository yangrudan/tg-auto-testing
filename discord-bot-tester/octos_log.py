import os
import json
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

import discord
from discord.ext import commands

# ======================
# 配置（通过环境变量）
# ======================
# 日志文件位置（测试/CI 中可通过环境变量指定）
LOG_FILE = os.environ.get("BOT_LOG_FILE", "bot_events.log")
LOG_MAX_BYTES = int(os.environ.get("BOT_LOG_MAX_BYTES", 10 * 1024 * 1024))
LOG_BACKUP_COUNT = int(os.environ.get("BOT_LOG_BACKUP_COUNT", 3))
# 若需将日志也输出到 stdout/stderr（CI 时可见），保持 True
LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT", "true").lower() in ("1", "true", "yes")

# Discord token（必需）
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("请先设置 DISCORD_BOT_TOKEN 环境变量。")

# ======================
# logging setup (JSON lines)
# ======================
logger = logging.getLogger("online_octos")
logger.setLevel(logging.INFO)

# Rotating file handler 写入 JSON 每行一条
fh = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8")
# 我们会直接写入 json.dumps(...) 的字符串，不依赖 Formatter 做 JSON
fh.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(fh)

if LOG_TO_STDOUT:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(sh)

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def central_log(event_type: str, payload: dict):
    """写入一条结构化 JSON 日志（每条为一行），方便测试脚本轮询/解析。"""
    entry = {"event": event_type, "timestamp": now_iso(), "payload": payload}
    try:
        # 确保为单行 JSON（便于 tail / grep / jq）
        logger.info(json.dumps(entry, ensure_ascii=False))
    except Exception:
        # 如果 JSON 序列化出错，降级为文本日志
        logger.exception("Failed to write structured log entry")

# ======================
# Discord bot setup
# ======================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    msg = {"bot_user": str(bot.user), "guilds": [g.name for g in bot.guilds]}
    central_log("bot_ready", msg)
    if LOG_TO_STDOUT:
        print(f"成功登录！我是 {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    """打印并写日志（包括收到的附件信息）。处理以 TEST_E2E: 开头的测试触发消息并在日志中记录解析后的 tc_id/correlation_id。"""
    payload = {
        "author": {"id": getattr(message.author, "id", None), "name": str(message.author)},
        "channel": {"id": getattr(message.channel, "id", None), "repr": str(message.channel)},
        "content": message.content,
        "message_id": getattr(message, "id", None),
        "attachments": [{"filename": a.filename, "url": a.url, "size": a.size} for a in message.attachments]
    }
    central_log("message_received", payload)

    # 如果是测试触发消息，解析并把解析结果也写入日志（不做外部回调）
    if isinstance(message.content, str) and message.content.startswith("TEST_E2E:"):
        try:
            body = message.content[len("TEST_E2E:"):].strip()
            parts = body.split("|", 2)
            tc_id = parts[0] if len(parts) >= 1 and parts[0] else "TC-UNKNOWN"
            correlation_id = parts[1] if len(parts) >= 2 and parts[1] else f"{message.author.id}-{int(datetime.utcnow().timestamp())}"
            extra = parts[2] if len(parts) >= 3 else None

            test_payload = {
                "tc_id": tc_id,
                "correlation_id": correlation_id,
                "author": {"id": message.author.id, "name": str(message.author)},
                "channel": {"id": getattr(message.channel, "id", None), "repr": str(message.channel)},
                "content": message.content,
                "extra": extra,
                "attachments": [{"filename": a.filename, "url": a.url, "size": a.size} for a in message.attachments],
                "message_id": getattr(message, "id", None),
            }
            central_log("test_trigger", test_payload)
        except Exception:
            central_log("test_trigger_parse_error", {"raw_content": message.content})

    # 保持 commands 扩展正常工作
    await bot.process_commands(message)

@bot.event
async def on_message_edit(before, after):
    central_log("message_edit", {
        "author": {"id": getattr(after.author, "id", None), "name": str(after.author)},
        "channel": {"id": getattr(after.channel, "id", None), "repr": str(after.channel)},
        "before": getattr(before, "content", None),
        "after": getattr(after, "content", None),
        "message_id": getattr(after, "id", None)
    })

@bot.event
async def on_message_delete(message: discord.Message):
    central_log("message_delete", {
        "author": {"id": getattr(message.author, "id", None), "name": str(message.author)},
        "channel": {"id": getattr(message.channel, "id", None), "repr": str(message.channel)},
        "content": getattr(message, "content", None),
        "message_id": getattr(message, "id", None)
    })

# 保留原命令
@bot.command()
async def whoami(ctx):
    await ctx.send(f"Your user id: {ctx.author.id}")

@bot.command()
async def ping(ctx):
    await ctx.send('Pong! 🏓')

if __name__ == "__main__":
    bot.run(TOKEN)