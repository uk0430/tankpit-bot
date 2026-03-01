import os
import asyncio
import hashlib
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

# ==============================
# ENVIRONMENT CONFIG
# ==============================

TOKEN = os.getenv("DISCORD_TOKEN")
SYNC_MODE = os.getenv("SYNC_MODE", "dev")  # dev or global
GUILD_ID = int(os.getenv("GUILD_ID", "0"))  # required in dev mode

SPRITE_PATH = "awards.gif"
FONT_PATH = "Gamer-Bold.otf"
CACHE_DIR = "cache"

os.makedirs(CACHE_DIR, exist_ok=True)

# ==============================
# BOT SETUP
# ==============================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ==============================
# DATA
# ==============================

AWARDS = {
    "MVP": (0, 0, 64, 64),
    "Sharpshooter": (64, 0, 128, 64),
    "Champion": (128, 0, 192, 64),
}

COLORS = {
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "blue": (0, 102, 255),
    "red": (220, 20, 60),
}

SIZES = {
    "default": 1,
    "medium": 1.4,
    "large": 1.8,
}

# ==============================
# PRELOAD ASSETS
# ==============================

SPRITE = Image.open(SPRITE_PATH).convert("RGBA")
FONT = ImageFont.truetype(FONT_PATH, 32)

print("Assets preloaded.")

# ==============================
# IMAGE RENDERING (NON-BLOCKING SAFE)
# ==============================

def render_image(username, award_name, color_name, size_name):
    coords = AWARDS[award_name]
    award = SPRITE.crop(coords)

    scale = SIZES[size_name]
    new_size = (int(award.width * scale), int(award.height * scale))
    award = award.resize(new_size, Image.NEAREST)

    width = max(award.width, 400)
    height = award.height + 120

    img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    text_color = COLORS[color_name]
    text_width = draw.textlength(username, font=FONT)

    draw.text(
        ((width - text_width) / 2, 30),
        username,
        fill=text_color,
        font=FONT
    )

    img.paste(
        award,
        ((width - award.width) // 2, 80),
        award
    )

    return img


def cache_key(username, award, color, size):
    raw = f"{username}-{award}-{color}-{size}"
    return hashlib.md5(raw.encode()).hexdigest() + ".png"


async def get_or_create_image(username, award, color, size):
    filename = cache_key(username, award, color, size)
    path = os.path.join(CACHE_DIR, filename)

    if os.path.exists(path):
        return path

    loop = asyncio.get_running_loop()
    img = await loop.run_in_executor(
        None,
        render_image,
        username,
        award,
        color,
        size
    )

    img.save(path)
    return path


# ==============================
# SLASH COMMAND
# ==============================

@tree.command(name="award", description="Generate TankPit award")
@app_commands.describe(
    award="Select award",
    color="Select color",
    size="Select size"
)
async def award(interaction: discord.Interaction, award: str, color: str, size: str):

    # ALWAYS ACKNOWLEDGE FIRST
    try:
        await interaction.response.defer(thinking=True)
    except discord.NotFound:
        print("Interaction expired before defer")
        return

    try:
        if award not in AWARDS:
            await interaction.followup.send("Invalid award.", ephemeral=True)
            return

        if color not in COLORS:
            await interaction.followup.send("Invalid color.", ephemeral=True)
            return

        if size not in SIZES:
            await interaction.followup.send("Invalid size.", ephemeral=True)
            return

        username = interaction.user.display_name
        path = await get_or_create_image(username, award, color, size)

        await interaction.followup.send(file=discord.File(path))

    except Exception as e:
        print("Error:", e)
        try:
            await interaction.followup.send("Something went wrong.", ephemeral=True)
        except:
            pass


# ==============================
# SYNC STRATEGY (PROFESSIONAL)
# ==============================

@bot.event
async def on_ready():

    if SYNC_MODE == "dev":
        if not GUILD_ID:
            raise ValueError("GUILD_ID required in dev mode")

        guild = discord.Object(id=GUILD_ID)
        await tree.sync(guild=guild)
        print("Synced to development guild only.")

    else:
        await tree.sync()
        print("Synced globally.")

    print(f"Logged in as {bot.user}")
    print(f"Total awards loaded: {len(AWARDS)}")


# ==============================
# RUN
# ==============================

bot.run(TOKEN)