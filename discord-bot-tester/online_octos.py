import discord
from discord.ext import commands
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'成功登录！我是 {bot.user}')

    # ==============================================
    # 机器人启动后 → 自动在 General 频道发消息
    # ==============================================
    for guild in bot.guilds:  # 遍历机器人加入的所有服务器
        print(f"正在检查服务器【{guild.name}】的频道...")
        # # 寻找名字叫 "general" 或 "General" 的频道o
        if guild.name == "TunedBayonet's server":
             general_channel = discord.utils.get(guild.text_channels, name="general")
             if general_channel:
                 await general_channel.send(f"✅ {bot.user.name} 已上线！小章鱼在吗???@octos_yy")
                 print(f"已在服务器【{guild.name}】的 General 频道发送上线消息")
             else:
                 print(f"在服务器【{guild.name}】中找不到 General 频道")


@bot.event
async def on_message(message: discord.Message):
    """打印所有收到的消息（包括来自机器人的消息）。
    同时确保命令可以被处理。"""
    ts = datetime.utcnow().isoformat(timespec='seconds')
    # message.channel 在 DM 中可能没有 name，这里直接打印 channel 对象
    print(f"[{ts}] MSG from {message.author} in {message.channel}: {message.content}")

    # 保持 commands 扩展正常工作
    await bot.process_commands(message)


@bot.event
async def on_message_edit(before, after):
    ts = datetime.utcnow().isoformat(timespec='seconds')
    print(f"[{ts}] EDIT by {after.author} in {after.channel}: '{before.content}' -> '{after.content}'")


@bot.event
async def on_message_delete(message: discord.Message):
    ts = datetime.utcnow().isoformat(timespec='seconds')
    print(f"[{ts}] DELETE by {message.author} in {message.channel}: id={message.id} content='{message.content}'")

@bot.command()
async def whoami(ctx):
    # ctx.author 是发送命令的用户
    await ctx.send(f"Your user id: {ctx.author.id}")

@bot.command()
async def ping(ctx):
    await ctx.send('Pong! 🏓')

# 3. 从环境变量读取 Token（更安全）
import os

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("请先设置 DISCORD_BOT_TOKEN 环境变量，或在代码中提供 token（不推荐将 token 写入源码）")

bot.run(TOKEN)