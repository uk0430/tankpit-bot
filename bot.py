import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import asyncio
import os
import hashlib

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")
SPRITE_PATH = "awards.gif"
FONT_PATH = "Gamer-Bold.otf"
CACHE_DIR = "cache"

os.makedirs(CACHE_DIR, exist_ok=True)

INTENTS = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=INTENTS)
tree = bot.tree

# =========================
# AWARD DATA (EXAMPLE)
# =========================

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

# =========================
# SAFE IMAGE RENDERING
# =========================

def render_award_image(username, award_name, color_name, size_name):
    sprite = Image.open(SPRITE_PATH).convert("RGBA")
    font = ImageFont.truetype(FONT_PATH, 32)

    coords = AWARDS[award_name]
    award = sprite.crop(coords)

    scale = SIZES[size_name]
    new_size = (int(award.width * scale), int(award.height * scale))
    award = award.resize(new_size, Image.NEAREST)

    padding = 40
    width = max(award.width, 400)
    height = award.height + 120

    img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # Username
    text_color = COLORS[color_name]
    text_width = draw.textlength(username, font=font)
    draw.text(
        ((width - text_width) / 2, 30),
        username,
        fill=text_color,
        font=font
    )

    # Award
    img.paste(
        award,
        ((width - award.width) // 2, 80),
        award
    )

    return img


# =========================
# CACHING
# =========================

def generate_cache_key(username, award, color, size):
    raw = f"{username}-{award}-{color}-{size}"
    return hashlib.md5(raw.encode()).hexdigest() + ".png"


async def get_or_create_image(username, award, color, size):
    filename = generate_cache_key(username, award, color, size)
    path = os.path.join(CACHE_DIR, filename)

    if os.path.exists(path):
        return path

    loop = asyncio.get_running_loop()
    img = await loop.run_in_executor(
        None,
        render_award_image,
        username,
        award,
        color,
        size
    )

    img.save(path)
    return path


# =========================
# SLASH COMMAND
# =========================

@tree.command(name="award", description="Generate a TankPit award card")
@app_commands.describe(
    award="Select award",
    color="Select color",
    size="Select size"
)
async def award(
    interaction: discord.Interaction,
    award: str,
    color: str,
    size: str
):
    try:
        # 🔥 MUST BE FIRST
        await interaction.response.defer(thinking=True)

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

        file = discord.File(path)
        await interaction.followup.send(file=file)

    except Exception as e:
        await interaction.followup.send(
            f"Error generating award: {str(e)}",
            ephemeral=True
        )


# =========================
# AUTOCOMPLETE
# =========================

@award.autocomplete("award")
async def award_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=name, value=name)
        for name in AWARDS
        if current.lower() in name.lower()
    ][:25]


@award.autocomplete("color")
async def color_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=name, value=name)
        for name in COLORS
        if current.lower() in name.lower()
    ][:25]


@award.autocomplete("size")
async def size_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=name, value=name)
        for name in SIZES
        if current.lower() in name.lower()
    ][:25]


# =========================
# READY EVENT
# =========================

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot ready as {bot.user}")


bot.run(TOKEN)