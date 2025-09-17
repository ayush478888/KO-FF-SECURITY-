import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from flask import Flask
from threading import Thread

# -------------------------
# Flask Keep-Alive
# -------------------------
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# -------------------------
# Discord Bot Setup
# -------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

OWNER_ID = 1389992203589521591  # replace with your Discord ID
LOG_CHANNEL_NAME = "security-logs"

whitelist = set([OWNER_ID])  # trusted users
recently_punished = {}       # cooldown memory

# -------------------------
# Helper Functions
# -------------------------
async def get_log_channel(guild):
    # If custom log channel set, use it
    if guild.id in log_channels:
        channel = guild.get_channel(log_channels[guild.id])
        if channel:
            return channel
    
    # fallback to "security-logs"
    channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if not channel:
        try:
            channel = await guild.create_text_channel(LOG_CHANNEL_NAME)
        except Exception:
            return None
    return channel

async def send_log(guild, message):
    channel = await get_log_channel(guild)
    if channel:
        await channel.send(message)

async def punish_and_revert(guild, executor, reason: str):
    now = datetime.utcnow().timestamp()
    # Cooldown: 15s per user
    if executor.id in recently_punished and now - recently_punished[executor.id] < 15:
        return
    recently_punished[executor.id] = now

    try:
        await guild.ban(executor, reason=reason, delete_message_days=0)
    except Exception:
        pass
    await send_log(guild, f"🚨 **Auto-ban** → {executor.mention} (`{executor.id}`) — {reason}")

def is_whitelisted(user: discord.Member):
    return user.id in whitelist or user.guild_permissions.administrator

# -------------------------
# Bot Events
# -------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_member_ban(guild, user):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        executor = entry.user
        if executor.id != OWNER_ID and not is_whitelisted(executor):
            await punish_and_revert(guild, executor, f"Unauthorized ban attempt on {user}")

@bot.event
async def on_member_remove(member):
    guild = member.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
        executor = entry.user
        if executor.id != OWNER_ID and not is_whitelisted(executor):
            await punish_and_revert(guild, executor, f"Unauthorized kick attempt on {member}")

@bot.event
async def on_guild_channel_create(channel):
    guild = channel.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
        executor = entry.user
        if executor.id != OWNER_ID and not is_whitelisted(executor):
            await punish_and_revert(guild, executor, "Unauthorized channel creation")
            await channel.delete()

@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        executor = entry.user
        if executor.id != OWNER_ID and not is_whitelisted(executor):
            await punish_and_revert(guild, executor, "Unauthorized channel deletion")

@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        executor = entry.user
        if executor.id != OWNER_ID and not is_whitelisted(executor):
            await punish_and_revert(guild, executor, f"Unauthorized role deletion ({role.name})")

@bot.event
async def on_guild_role_update(before, after):
    guild = before.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
        executor = entry.user
        if executor.id != OWNER_ID and not is_whitelisted(executor):
            await punish_and_revert(guild, executor, f"Unauthorized role update ({before.name})")

# -------------------------
# Configurable Log Channel
# -------------------------
log_channels = {}  # stores guild_id -> channel_id

# -------------------------
# Commands
# -------------------------
@bot.command()
async def setlog(ctx, channel: discord.TextChannel):
    """Set a custom log channel for this server"""
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ You are not allowed to use this command.")

    log_channels[ctx.guild.id] = channel.id
    await ctx.send(f"✅ Log channel set to {channel.mention}")

@bot.command()
async def showlog(ctx):
    """Show current log channel"""
    channel = await get_log_channel(ctx.guild)
    if channel:
        await ctx.send(f"📑 Current log channel is {channel.mention}")
    else:
        await ctx.send("⚠️ No log channel found.")

@bot.command()
async def whitelist_add(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ You are not allowed to use this command.")
    whitelist.add(member.id)
    await ctx.send(f"✅ {member.mention} has been whitelisted.")

@bot.command()
async def whitelist_remove(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ You are not allowed to use this command.")
    whitelist.discard(member.id)
    await ctx.send(f"✅ {member.mention} has been removed from whitelist.")

@bot.command()
async def whitelist_show(ctx):
    ids = ", ".join([str(uid) for uid in whitelist])
    await ctx.send(f"👥 Whitelisted IDs: {ids}")

# -------------------------
# Run the Bot
# -------------------------
keep_alive()  # Start the Flask server for UptimeRobot
bot.run("YOUR_DISCORD_BOT_TOKEN")
