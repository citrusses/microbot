# bot.py
import discord
from discord.ext import commands
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

REACTION_ROUTES = {
    "📌": 123456789012345678,  # Replace with your channel IDs
    "🧷": 234567890123456789,
    "customemojiid": 345678901234567890  # Replace with actual custom emoji ID
}

REPOST_FILE = "reposted.json"

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load reposted messages from file
if os.path.exists(REPOST_FILE):
    with open(REPOST_FILE, "r") as f:
        reposted = json.load(f)
else:
    reposted = []

def save_repost(message_id, repost_id, emoji):
    reposted.append({"original": message_id, "repost": repost_id, "emoji": emoji})
    with open(REPOST_FILE, "w") as f:
        json.dump(reposted, f, indent=2)

def get_og_metadata(url):
    try:
        res = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.find("meta", property="og:title") or soup.find("title")
        desc = soup.find("meta", property="og:description")
        image = soup.find("meta", property="og:image")
        return {
            "title": title["content"] if title and title.has_attr("content") else title.text if title else None,
            "desc": desc["content"] if desc else None,
            "image": image["content"] if image else None,
        }
    except Exception as e:
        print("OpenGraph fetch failed:", e)
        return {}

@bot.event
async def on_ready():
    synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"🔧 Synced slash commands: {len(synced)}")
    print(f"✅ Logged in as {bot.user}")

@bot.tree.command(name="repoststats", description="Show how many messages have been reposted", guild=discord.Object(id=GUILD_ID))
async def repoststats(interaction: discord.Interaction, full: bool = False):
    total = len(reposted)
    recent = reposted[-5:] if not full else reposted
    msg = f"📊 Total reposted messages: {total}\n"
    msg += "\n".join(f"📎 {entry['original']} ➜ {entry['repost']}" for entry in recent)
    await interaction.response.send_message(msg or "No reposts yet.", ephemeral=True)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    emoji_key = str(payload.emoji.id) if payload.emoji.id else payload.emoji.name
    if emoji_key not in REACTION_ROUTES:
        return

    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    # Prevent duplicate repost
    if any(entry['original'] == str(message.id) for entry in reposted):
        return

    dest_channel = bot.get_channel(REACTION_ROUTES[emoji_key])
    if not isinstance(dest_channel, discord.TextChannel):
        return

    jump_url = message.jump_url
    content = message.content or "*[No content]*"

    embed = discord.Embed(description=content, timestamp=message.created_at, color=0xFFCC00)
    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    embed.add_field(name="🔗 Jump to Original Message", value=f"[Click here]({jump_url})", inline=False)

    # OG metadata (first link only)
    match = re.search(r"https?://\S+", content)
    if match:
        meta = get_og_metadata(match.group())
        if meta.get("title"):
            embed.add_field(name="🔗 Link Preview", value=f"[{meta['title']}]({match.group()})", inline=False)
        if meta.get("desc"):
            embed.add_field(name="Description", value=meta["desc"], inline=False)
        if meta.get("image"):
            embed.set_image(url=meta["image"])

    if message.attachments:
        image = next((a for a in message.attachments if a.content_type and a.content_type.startswith("image")), None)
        if image:
            embed.set_image(url=image.url)

    repost_msg = await dest_channel.send(embed=embed)
    save_repost(str(message.id), str(repost_msg.id), emoji_key)

bot.run(TOKEN)
