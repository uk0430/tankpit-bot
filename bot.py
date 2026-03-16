import asyncio
import os
import hashlib
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log"),
    ]
)
log = logging.getLogger(__name__)

# ==========================
# ENV
# ==========================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

if not TOKEN:
    raise ValueError("DISCORD_TOKEN missing")

# ==========================
# CONFIG
# ==========================

SPRITE_PATH = "assets/awards.gif"
FONT_PATH = "fonts/Gamer-Bold.otf"
ICON_HEIGHT = 16
CACHE_FOLDER = "cache"

os.makedirs(CACHE_FOLDER, exist_ok=True)

# ==========================
# COLORS
# ==========================

OFFICIAL_COLORS = {
    "Orange": (255, 144, 0),
    "Purple": (223, 0, 224),
    "Blue": (0, 0, 224),
    "Red": (224, 0, 0),
}

TANKPIT_BG = (255, 255, 224)
TANKPIT_TEXT = (255, 144, 0)

# ==========================
# SIZE OPTIONS
# ==========================

SIZE_OPTIONS = {
    "Default": 1.0,
    "Medium": 1.3,
    "Large": 1.6,
}

# ==========================
# SPRITE DATA
# ==========================

SPRITE_DATA = {
    "a0-1": {"x": 13, "w": 13},
    "a0-2": {"x": 26, "w": 13},
    "a0-3": {"x": 39, "w": 13},
    "a1-1": {"x": 82, "w": 30},
    "a1-2": {"x": 112, "w": 30},
    "a1-3": {"x": 142, "w": 30},
    "a2-1": {"x": 181, "w": 9},
    "a2-2": {"x": 190, "w": 9},
    "a2-3": {"x": 199, "w": 9},
    "a3-1": {"x": 217, "w": 9},
    "a3-2": {"x": 226, "w": 9},
    "a3-3": {"x": 235, "w": 9},
    "a4-3": {"x": 277, "w": 11},
    "a5-1": {"x": 301, "w": 13},
    "a5-2": {"x": 314, "w": 13},
    "a5-3": {"x": 327, "w": 13},
    "a6-1": {"x": 340, "w": 11},
    "a7-1": {"x": 351, "w": 11},
    "a8-1": {"x": 376, "w": 14},
}

# ==========================
# AWARDS
# ==========================

AWARDS = {
    "single_star": {"class": "a0-1", "display": "Single Star"},
    "double_star": {"class": "a0-2", "display": "Double Star"},
    "triple_star": {"class": "a0-3", "display": "Triple Star"},
    "bronze_tank": {"class": "a1-1", "display": "Bronze Tank"},
    "silver_tank": {"class": "a1-2", "display": "Silver Tank"},
    "golden_tank": {"class": "a1-3", "display": "Golden Tank"},
    "combat_honor": {"class": "a2-1", "display": "Combat Honor Medal"},
    "battle_honor": {"class": "a2-2", "display": "Battle Honor Medal"},
    "heroic_honor": {"class": "a2-3", "display": "Heroic Honor Medal"},
    "shining_sword": {"class": "a3-1", "display": "Shining Sword"},
    "battered_sword": {"class": "a3-2", "display": "Battered Sword"},
    "rusty_sword": {"class": "a3-3", "display": "Rusty Sword"},
    "defender_truth": {"class": "a4-3", "display": "Defender of the Truth"},
    "bronze_cup": {"class": "a5-1", "display": "Bronze Cup"},
    "silver_cup": {"class": "a5-2", "display": "Silver Cup"},
    "gold_cup": {"class": "a5-3", "display": "Gold Cup"},
    "purple_heart": {"class": "a6-1", "display": "Purple Heart"},
    "war_correspondent": {"class": "a7-1", "display": "War Correspondent"},
    "lightbulb": {"class": "a8-1", "display": "Lightbulb"},
}

# ==========================
# CATEGORY ORDER
# ==========================

CATEGORIES = {
    "stars": ["single_star", "double_star", "triple_star"],
    "tanks": ["bronze_tank", "silver_tank", "golden_tank"],
    "medals": ["combat_honor", "battle_honor", "heroic_honor"],
    "swords": ["shining_sword", "battered_sword", "rusty_sword"],
    "dot": ["defender_truth"],
    "cups": ["bronze_cup", "silver_cup", "gold_cup"],
    "ph": ["purple_heart"],
    "wc": ["war_correspondent"],
    "lb": ["lightbulb"],
}

CATEGORY_ORDER = ["stars","tanks","medals","swords","dot","cups","ph","wc","lb"]

# ==========================
# HELPERS
# ==========================

def sort_awards(selected):
    ordered = []
    for category in CATEGORY_ORDER:
        for award in CATEGORIES[category]:
            if award in selected:
                ordered.append(award)
    return ordered

def crop_award(sprite, class_name):
    data = SPRITE_DATA[class_name]
    return sprite.crop((data["x"], 0, data["x"] + data["w"], ICON_HEIGHT))

def generate_award_banner(name, award_keys, color, banner=False, size_mode="Default"):

    scale = SIZE_OPTIONS[size_mode]

    cache_string = f"{name}_{sorted(award_keys)}_{color}_{banner}_{size_mode}"
    cache_hash = hashlib.md5(cache_string.encode()).hexdigest()
    cache_path = os.path.join(CACHE_FOLDER, f"{cache_hash}.png")

    if os.path.exists(cache_path):
        return cache_path

    sprite = Image.open(SPRITE_PATH).convert("RGBA")
    font = ImageFont.truetype(FONT_PATH, int(18 * scale))

    padding_x = int(14 * scale)
    padding_y = int(6 * scale)
    vertical_gap = int(4 * scale)
    spacing = int(2 * scale)

    temp = Image.new("RGBA",(1,1))
    draw = ImageDraw.Draw(temp)
    bbox = draw.textbbox((0,0), name, font=font)
    text_width = bbox[2]-bbox[0]
    text_height = bbox[3]-bbox[1]

    icons = []
    for key in award_keys:
        icon = crop_award(sprite, AWARDS[key]["class"])
        w,h = icon.size
        icon = icon.resize((int(w*scale), int(h*scale)), Image.NEAREST)
        icons.append(icon)

    awards_width = sum(icon.width for icon in icons)
    awards_width += spacing*(len(icons)-1) if icons else 0

    width = max(text_width, awards_width) + padding_x*2
    height = padding_y*2 + text_height + (vertical_gap if icons else 0) + (icons[0].height if icons else 0)

    if banner:
        img = Image.new("RGBA",(width,height), TANKPIT_BG+(255,))
        draw = ImageDraw.Draw(img)
        draw.text(((width-text_width)//2,padding_y), name, fill=TANKPIT_TEXT, font=font)
    else:
        img = Image.new("RGBA",(width,height),(0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.text(((width-text_width)//2,padding_y), name, fill=color, font=font)

    x = (width-awards_width)//2
    y = padding_y+text_height+vertical_gap

    for icon in icons:
        img.paste(icon,(x,y),icon)
        x += icon.width+spacing

    img.save(cache_path)
    return cache_path

# ==========================
# DISCORD SETUP
# ==========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
GUILD = discord.Object(id=GUILD_ID)

# ==========================
# UI
# ==========================

def _award_content(name: str) -> str:
    return (
        f"**Configuring banner for:** {name}\n"
        "Select awards, color, and size, then click **Generate Banner**."
    )


class ChangeNameModal(discord.ui.Modal, title="Change Tank Name"):
    new_name = discord.ui.TextInput(
        label="Tank or Player Name",
        placeholder="e.g. Grimlock, Stonerock...",
        min_length=1,
        max_length=64,
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        name = self.new_name.value.strip().strip(",")
        self.parent_view.tank_name = name
        await interaction.response.defer()
        if self.parent_view.message:
            await self.parent_view.message.edit(
                content=_award_content(name),
                view=self.parent_view,
            )


class AwardSelectionView(discord.ui.View):
    def __init__(self, tank_name: str):
        super().__init__(timeout=300)
        self.tank_name = tank_name
        self.message = None

        awards_options = [
            discord.SelectOption(label=info["display"], value=key)
            for key, info in AWARDS.items()
        ]
        self.awards_select = discord.ui.Select(
            placeholder="Select awards...",
            min_values=0,
            max_values=len(awards_options),
            options=awards_options,
            row=0,
        )
        self.awards_select.callback = self._noop

        self.color_select = discord.ui.Select(
            placeholder="Text color (default: Blue)...",
            min_values=0,
            max_values=1,
            options=[
                discord.SelectOption(label=name, value=name)
                for name in OFFICIAL_COLORS
            ],
            row=1,
        )
        self.color_select.callback = self._noop

        self.size_select = discord.ui.Select(
            placeholder="Banner size (default: Default)...",
            min_values=0,
            max_values=1,
            options=[
                discord.SelectOption(label=name, value=name)
                for name in SIZE_OPTIONS
            ],
            row=2,
        )
        self.size_select.callback = self._noop

        self.add_item(self.awards_select)
        self.add_item(self.color_select)
        self.add_item(self.size_select)

    async def _noop(self, interaction: discord.Interaction):
        await interaction.response.defer()

    @discord.ui.button(label="Generate Banner", style=discord.ButtonStyle.primary, row=3)
    async def generate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        award_keys = self.awards_select.values or []
        sorted_awards = sort_awards(award_keys)
        color_val = self.color_select.values[0] if self.color_select.values else "Blue"
        size_val = self.size_select.values[0] if self.size_select.values else "Default"
        chosen_color = OFFICIAL_COLORS[color_val]

        try:
            loop = asyncio.get_event_loop()
            image_path = await loop.run_in_executor(
                None,
                generate_award_banner,
                self.tank_name,
                sorted_awards,
                chosen_color,
                False,
                size_val,
            )
            await interaction.followup.send(file=discord.File(image_path))
            log.info(f"/award: {self.tank_name} | awards={sorted_awards} | color={color_val} | size={size_val}")
        except Exception as e:
            log.exception(f"/award failed for '{self.tank_name}': {e}")
            await interaction.followup.send(f"Error generating banner: `{e}`", ephemeral=True)

    @discord.ui.button(label="Change Name", style=discord.ButtonStyle.secondary, row=3)
    async def change_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChangeNameModal(self))


# ==========================
# SLASH COMMAND
# ==========================

@tree.command(name="award", description="Generate a TankPit award banner for a tank or player", guild=GUILD)
@app_commands.describe(tank_name="Tank or player name (e.g. Grimlock)")
async def award(interaction: discord.Interaction, tank_name: str):
    name = tank_name.strip().strip(",")
    view = AwardSelectionView(name)
    await interaction.response.send_message(_award_content(name), view=view, ephemeral=True)
    view.message = await interaction.original_response()

# ==========================
# READY + SYNC
# ==========================

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    log.info(f"Logged in as {bot.user}")
    log.info("Award command synced.")

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.exception(f"Unhandled app command error: {error}")
    if not interaction.response.is_done():
        await interaction.response.send_message(f"Unexpected error: `{error}`", ephemeral=True)
    else:
        await interaction.followup.send(f"Unexpected error: `{error}`", ephemeral=True)

print("Bot starting...")
bot.run(TOKEN)