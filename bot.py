import asyncio
import json
import os
import hashlib
import logging
import time
import numpy as np
import requests
from dotenv import load_dotenv

import aiohttp
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
GUILD_ID_2 = int(os.getenv("GUILD_ID_2"))

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
# RAG DATA
# ==========================

with open("/home/ukhan/tankpit-ai/bible_chunks.json") as _f:
    _raw_chunks = json.load(_f)

BIBLE_TEXTS = [c["text"] for c in _raw_chunks]
BIBLE_EMBEDDINGS = np.array([c["embedding"] for c in _raw_chunks], dtype=np.float32)
# Pre-normalise for fast cosine similarity via dot product
_norms = np.linalg.norm(BIBLE_EMBEDDINGS, axis=1, keepdims=True)
BIBLE_EMBEDDINGS_NORM = BIBLE_EMBEDDINGS / np.where(_norms == 0, 1, _norms)

EMBED_URL = "http://127.0.0.1:8081/v1/embeddings"
LLM_URL   = "http://127.0.0.1:8080/v1/chat/completions"

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

# Awards array index → ordered keys (matches AWARD_TIERS / API awards array)
AWARD_KEYS_BY_INDEX = [
    ["single_star",      "double_star",       "triple_star"],
    ["bronze_tank",      "silver_tank",       "golden_tank"],
    ["combat_honor",     "battle_honor",      "heroic_honor"],
    ["shining_sword",    "battered_sword",    "rusty_sword"],
    ["defender_truth",   "defender_truth",    "defender_truth"],
    ["bronze_cup",       "silver_cup",        "gold_cup"],
    ["purple_heart",     "purple_heart",      "purple_heart"],
    ["war_correspondent","war_correspondent", "war_correspondent"],
    ["lightbulb",        "lightbulb",         "lightbulb"],
]

# ==========================
# LEADERBOARD IMAGE CONSTANTS
# ==========================

_LB_BG          = (15,  21,  26)   # #0F151A
_LB_HEADER_BG   = (62,  84,  99)   # #3e5463
_LB_COL_BG      = (42,  56,  64)   # #2a3840
_LB_MUTED       = (140, 168, 180)
_LB_FACTION     = {
    "red":    (255, 102, 102),
    "purple": (204, 102, 204),
    "blue":   (102, 102, 255),
    "orange": (255, 204, 102),
}
_LB_ROW_DEFAULT = (35, 50, 60)
_LB_BLACK       = (0,   0,   0)
_LB_LIGHT       = (220, 230, 235)

_LB_W        = 700
_LB_HEADER_H = 54
_LB_COLHDR_H = 28
_LB_ROW_H    = 36
_LB_ROW_GAP  = 3
_LB_FOOTER_H = 30

# Column x positions
_LB_COL_PLACE = 12
_LB_COL_NAME  = 55
_LB_COL_RANK  = 268
_LB_COL_AWARD = 390

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


def generate_leaderboard_image(entries: list, title: str, page: int = 1, total_pages: int = 1) -> str:
    cache_string = f"{title}_p{page}_{json.dumps(entries, sort_keys=True)}"
    cache_hash = hashlib.md5(cache_string.encode()).hexdigest()
    cache_path = os.path.join(CACHE_FOLDER, f"lb_{cache_hash}.png")
    if os.path.exists(cache_path):
        return cache_path

    n = len(entries)
    total_h = _LB_HEADER_H + _LB_COLHDR_H + n * _LB_ROW_H + max(0, n - 1) * _LB_ROW_GAP + _LB_FOOTER_H

    img  = Image.new("RGB", (_LB_W, total_h), _LB_BG)
    draw = ImageDraw.Draw(img)

    font_title        = ImageFont.truetype(FONT_PATH, 28)
    font_col          = ImageFont.truetype(FONT_PATH, 12)
    font_name         = ImageFont.truetype(FONT_PATH, 13)
    font_rank         = ImageFont.truetype(FONT_PATH, 11)
    font_place_lg     = ImageFont.truetype(FONT_PATH, 20)   # #1
    font_place_md     = ImageFont.truetype(FONT_PATH, 16)   # #2-3
    font_place_sm     = ImageFont.truetype(FONT_PATH, 14)   # rest

    # Header
    draw.rectangle([0, 0, _LB_W, _LB_HEADER_H], fill=_LB_HEADER_BG)
    tb = draw.textbbox((0, 0), title, font=font_title)
    draw.text(
        ((_LB_W - (tb[2] - tb[0])) // 2, (_LB_HEADER_H - (tb[3] - tb[1])) // 2),
        title, fill=(255, 255, 255), font=font_title,
    )

    # Column headers
    cy = _LB_HEADER_H
    draw.rectangle([0, cy, _LB_W, cy + _LB_COLHDR_H], fill=_LB_COL_BG)
    for label, cx in [("#", _LB_COL_PLACE), ("Name", _LB_COL_NAME), ("Rank", _LB_COL_RANK), ("Awards", _LB_COL_AWARD)]:
        draw.text((cx, cy + 8), label, fill=_LB_MUTED, font=font_col)

    sprite = Image.open(SPRITE_PATH).convert("RGBA")
    ry = _LB_HEADER_H + _LB_COLHDR_H

    for entry in entries:
        placing = entry.get("placing", 0)
        name    = str(entry.get("name", "Unknown"))
        rank    = str(entry.get("rank") or "").capitalize()
        ck      = (entry.get("color") or "").lower()
        awards  = entry.get("awards") or []

        bg   = _LB_FACTION.get(ck, _LB_ROW_DEFAULT)
        tcol = _LB_BLACK if ck in _LB_FACTION else _LB_LIGHT

        draw.rectangle([0, ry, _LB_W, ry + _LB_ROW_H], fill=bg)

        # Placing number
        if placing == 1:
            pf = font_place_lg
        elif placing in (2, 3):
            pf = font_place_md
        else:
            pf = font_place_sm
        ps = str(placing)
        pb = draw.textbbox((0, 0), ps, font=pf)
        draw.text(
            (_LB_COL_PLACE + (35 - (pb[2] - pb[0])) // 2, ry + (_LB_ROW_H - (pb[3] - pb[1])) // 2),
            ps, fill=tcol, font=pf,
        )

        # Name
        nb = draw.textbbox((0, 0), name, font=font_name)
        draw.text((_LB_COL_NAME, ry + (_LB_ROW_H - (nb[3] - nb[1])) // 2), name, fill=tcol, font=font_name)

        # Rank
        rb = draw.textbbox((0, 0), rank, font=font_rank)
        draw.text((_LB_COL_RANK, ry + (_LB_ROW_H - (rb[3] - rb[1])) // 2), rank, fill=tcol, font=font_rank)

        # Award icons
        ax = _LB_COL_AWARD
        ay = ry + (_LB_ROW_H - ICON_HEIGHT) // 2
        for i, val in enumerate(awards):
            if val and i < len(AWARD_KEYS_BY_INDEX):
                keys = AWARD_KEYS_BY_INDEX[i]
                key  = keys[min(val, len(keys)) - 1]
                icon = crop_award(sprite, AWARDS[key]["class"])
                img.paste(icon, (ax, ay), icon)
                ax += icon.width + 2

        ry += _LB_ROW_H + _LB_ROW_GAP

    # Footer
    ft = f"Page {page} of {total_pages}  •  /leaderboard year:... top:..."
    draw.text((_LB_COL_PLACE, total_h - _LB_FOOTER_H + 8), ft, fill=_LB_MUTED, font=font_col)

    img.save(cache_path)
    return cache_path

# ==========================
# DISCORD SETUP
# ==========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
GUILD = discord.Object(id=GUILD_ID)
GUILD2 = discord.Object(id=GUILD_ID_2)

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

tree.add_command(award, guild=GUILD2)

# ==========================
# TANK LOOKUP HELPERS
# ==========================

TANKPIT_FIND_URL = "https://tankpit.com/api/find_tank"
TANKPIT_PROFILE_URL = "https://tankpit.com/api/tank"

# awards array index → (category label, [tier labels by value 1,2,3])
AWARD_TIERS = [
    ("Stars",   ["Single Star", "Double Star", "Triple Star"]),
    ("Tank",    ["Bronze Tank", "Silver Tank", "Golden Tank"]),
    ("Medal",   ["Combat Honor", "Battle Honor", "Heroic Honor"]),
    ("Sword",   ["Shining Sword", "Battered Sword", "Rusty Sword"]),
    ("Special", ["Defender of Truth", "Defender of Truth", "Defender of Truth"]),
    ("Cup",     ["Bronze Cup", "Silver Cup", "Gold Cup"]),
    ("Special", ["Purple Heart", "Purple Heart", "Purple Heart"]),
    ("Special", ["War Correspondent", "War Correspondent", "War Correspondent"]),
    ("Special", ["Lightbulb", "Lightbulb", "Lightbulb"]),
]

_API_TIMEOUT = aiohttp.ClientTimeout(total=10)


def decode_awards(awards: list) -> str:
    """Convert raw awards array (e.g. [3,3,3,2,3,3,0,1,0]) to readable names."""
    names = []
    for i, val in enumerate(awards):
        if val and i < len(AWARD_TIERS):
            _, tiers = AWARD_TIERS[i]
            names.append(tiers[min(val, 3) - 1])
    return ", ".join(names) if names else "None"


async def fetch_tank_search(name: str) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(TANKPIT_FIND_URL, params={"name": name}, timeout=_API_TIMEOUT) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data if isinstance(data, list) else [data]


async def fetch_tank_profile(tank_id: int) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(TANKPIT_PROFILE_URL, params={"tank_id": tank_id}, timeout=_API_TIMEOUT) as resp:
            resp.raise_for_status()
            return await resp.json()


def build_tank_embed(profile: dict) -> discord.Embed:
    name = profile.get("name", "Unknown")
    color_name = (profile.get("main_color") or "").lower()
    embed_color = {"blue": 0x0000E0, "red": 0xE00000, "orange": 0xFF9000, "purple": 0xDF00E0}.get(color_name, 0xFF9000)

    embed = discord.Embed(title=name, color=embed_color)

    # Row 1 — identity
    if color_name:
        embed.add_field(name="Color", value=color_name.capitalize(), inline=True)
    if country := profile.get("country"):
        embed.add_field(name="Country", value=country, inline=True)
    if ping := profile.get("ping"):
        embed.add_field(name="Ping", value=ping, inline=True)

    # Row 2 — gameplay
    if fav_map := profile.get("favorite_map"):
        embed.add_field(name="Favorite Map", value=fav_map, inline=True)
    if bf_name := profile.get("bf_tank_name"):
        embed.add_field(name="Battlefield Tank", value=bf_name, inline=True)

    # Tournament victories
    tv = profile.get("tournament_victories") or {}
    gold_n   = len(tv.get("gold",   []))
    silver_n = len(tv.get("silver", []))
    bronze_n = len(tv.get("bronze", []))
    if gold_n or silver_n or bronze_n:
        embed.add_field(
            name="Tournament Victories",
            value=f"🥇 {gold_n}  🥈 {silver_n}  🥉 {bronze_n}",
            inline=False,
        )

    # Awards
    raw_awards = profile.get("awards") or []
    if raw_awards:
        embed.add_field(name="Awards", value=decode_awards(raw_awards), inline=False)

    # Bio
    if bio := profile.get("profile"):
        embed.add_field(name="Profile", value=bio, inline=False)

    if tank_id := profile.get("tank_id"):
        embed.set_footer(text=f"Tank ID: {tank_id}")

    return embed


class TankSelectView(discord.ui.View):
    """Shown when find_tank returns multiple results — lets user pick one."""

    def __init__(self, results: list[dict]):
        super().__init__(timeout=60)
        self.results = results
        options = [
            discord.SelectOption(
                label=t.get("name", f"Tank {i+1}")[:100],
                value=str(i),
                description=(f"ID: {t['tank_id']}" if t.get("tank_id") else None),
            )
            for i, t in enumerate(results[:25])
        ]
        select = discord.ui.Select(placeholder="Multiple tanks found — pick one…", options=options)
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        idx = int(interaction.data["values"][0])
        tank_id = self.results[idx].get("tank_id")
        try:
            profile = await fetch_tank_profile(tank_id)
        except Exception as e:
            log.exception(f"TankSelectView profile fetch failed (id={tank_id}): {e}")
            await interaction.edit_original_response(content=f"Failed to load profile: `{e}`", embed=None, view=None)
            return
        await interaction.edit_original_response(content=None, embed=build_tank_embed(profile), view=None)


# ==========================
# /tank COMMAND
# ==========================

@tree.command(name="tank", description="Look up a TankPit player profile by name", guild=GUILD)
@app_commands.describe(tank_name="Tank or player name to search for")
async def tank_lookup(interaction: discord.Interaction, tank_name: str):
    await interaction.response.send_message("Searching…", ephemeral=True)
    try:
        results = await fetch_tank_search(tank_name.strip())
    except aiohttp.ClientResponseError as e:
        log.warning(f"/tank search error for '{tank_name}': {e.status} {e.message}")
        await interaction.edit_original_response(content=f"API error: `{e.status} {e.message}`")
        return
    except Exception as e:
        log.exception(f"/tank failed for '{tank_name}': {e}")
        await interaction.edit_original_response(content=f"Failed to reach TankPit API: `{e}`")
        return

    if not results:
        await interaction.edit_original_response(content=f"No tanks found for **{tank_name}**.")
        return

    if len(results) > 1:
        view = TankSelectView(results)
        await interaction.edit_original_response(
            content=f"Found **{len(results)}** tanks matching **{tank_name}** — pick one:",
            view=view,
        )
        return

    # Single result — fetch full profile
    tank_id = results[0].get("tank_id")
    try:
        profile = await fetch_tank_profile(tank_id)
    except aiohttp.ClientResponseError as e:
        log.warning(f"/tank profile error (id={tank_id}): {e.status} {e.message}")
        await interaction.edit_original_response(content=f"API error fetching profile: `{e.status} {e.message}`")
        return
    except Exception as e:
        log.exception(f"/tank profile fetch failed (id={tank_id}): {e}")
        await interaction.edit_original_response(content=f"Failed to load profile: `{e}`")
        return

    log.info(f"/tank: {profile.get('name')} (id={tank_id})")
    await interaction.edit_original_response(content=None, embed=build_tank_embed(profile))

tree.add_command(tank_lookup, guild=GUILD2)

# ==========================
# /leaderboard COMMAND
# ==========================

LEADERBOARD_URL = "https://tankpit.com/api/leaderboards"

RANK_EMOJI = {
    "general": "⭐",
    "colonel": "🔰",
    "major": "🔹",
    "captain": "▪️",
}

COLOR_EMOJI = {
    "blue": "🔵",
    "red": "🔴",
    "orange": "🟠",
    "purple": "🟣",
}


async def fetch_leaderboard(year: str = "overall", page: int = 1) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            LEADERBOARD_URL,
            params={"leaderboard": year, "page": page},
            timeout=_API_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


@tree.command(name="leaderboard", description="Show the TankPit leaderboard", guild=GUILD)
@app_commands.describe(
    year="Year (e.g. 2024) or 'overall' (default)",
    top="How many to show (default 10, max 25)",
)
async def leaderboard(
    interaction: discord.Interaction,
    year: str = "overall",
    top: int = 10,
):
    top = max(1, min(top, 25))
    await interaction.response.defer()
    try:
        data = await fetch_leaderboard(year=year)
    except aiohttp.ClientResponseError as e:
        await interaction.followup.send(f"API error: `{e.status} {e.message}`")
        return
    except Exception as e:
        log.exception(f"/leaderboard failed: {e}")
        await interaction.followup.send(f"Failed to reach TankPit API: `{e}`")
        return

    results = data.get("results", [])[:top]
    if not results:
        await interaction.followup.send(f"No leaderboard data for **{year}**.")
        return

    title       = f"TankPit Leaderboard — {year.capitalize()}"
    total_pages = data.get("total_pages", 1)

    image_path = await asyncio.to_thread(generate_leaderboard_image, results, title, 1, total_pages)

    # Small embed with top-3 clickable names
    embed = discord.Embed(color=0xFF9000)
    top3_lines = []
    for entry in results[:3]:
        placing  = entry.get("placing")
        name     = entry.get("name", "Unknown")
        tank_id  = entry.get("tank_id")
        url      = f"https://tankpit.com/tank/{tank_id}" if tank_id else "https://tankpit.com"
        medal    = {1: "🥇", 2: "🥈", 3: "🥉"}.get(placing, "")
        top3_lines.append(f"{medal} [{name}]({url})")
    embed.description = "\n".join(top3_lines)
    embed.set_footer(text=f"Page 1 of {total_pages} • /leaderboard year:{year} top:{top}")

    await interaction.followup.send(file=discord.File(image_path), embed=embed)
    log.info(f"/leaderboard: year={year} top={top}")

tree.add_command(leaderboard, guild=GUILD2)

# ==========================
# /ask COMMAND
# ==========================

_ASK_CACHE: dict[str, tuple[str, float]] = {}  # question -> (answer, expiry_timestamp)
_ASK_RANK_KW = {"leaderboard", "rank", "ranking", "top", "best", "score", "place", "placing"}


def _ask_ttl(question: str) -> float:
    """5-min TTL for leaderboard/rank questions, 1-hour for everything else."""
    return 300.0 if set(question.lower().split()) & _ASK_RANK_KW else 3600.0


def _rag_query(question: str) -> str:
    """Blocking: embed question, find top-3 chunks, query Mistral. Returns answer string."""
    # 1. Embed the question
    embed_resp = requests.post(
        EMBED_URL,
        json={"input": question, "model": "text-embedding-nomic-embed-text-v1.5"},
        timeout=30,
    )
    embed_resp.raise_for_status()
    q_vec = np.array(embed_resp.json()["data"][0]["embedding"], dtype=np.float32)
    q_norm = q_vec / (np.linalg.norm(q_vec) or 1.0)

    # 2. Cosine similarity against all chunks
    scores = BIBLE_EMBEDDINGS_NORM @ q_norm
    top_idx = np.argsort(scores)[-3:][::-1]
    context = "\n\n---\n\n".join(BIBLE_TEXTS[i] for i in top_idx)

    # 3. Query Mistral
    system_prompt = (
        "You are a helpful assistant for the TankPit gaming community. "
        "Answer the user's question using only the context provided below. "
        "If the answer is not in the context, say so.\n\n"
        f"Context:\n{context}"
    )
    llm_resp = requests.post(
        LLM_URL,
        json={
            "model": "mistral",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            "temperature": 0.2,
        },
        timeout=60,
    )
    llm_resp.raise_for_status()
    return llm_resp.json()["choices"][0]["message"]["content"]


@tree.command(name="ask", description="Ask a question about TankPit (AI-powered)", guild=GUILD)
@app_commands.describe(
    question="Your question about TankPit",
    private="Only you can see the answer (default: False)",
)
async def ask(interaction: discord.Interaction, question: str, private: bool = False):
    await interaction.response.defer(ephemeral=private)

    # In-memory cache check
    cached = _ASK_CACHE.get(question)
    if cached and time.time() < cached[1]:
        answer = cached[0]
        log.info(f"/ask (cached): q={question!r}")
    else:
        try:
            answer = await asyncio.to_thread(_rag_query, question)
        except Exception as e:
            log.exception(f"/ask failed for '{question}': {e}")
            await interaction.followup.send(f"Error querying AI: `{e}`", ephemeral=True)
            return
        _ASK_CACHE[question] = (answer, time.time() + _ask_ttl(question))

    if len(answer) > 4096:
        answer = answer[:4093] + "…"

    embed = discord.Embed(
        title=question[:256],
        description=answer,
        color=0xFF9000,
    )
    embed.set_author(
        name=interaction.user.display_name,
        icon_url=str(interaction.user.display_avatar.url),
    )

    log.info(f"/ask: q={question!r} private={private}")
    await interaction.followup.send(embed=embed, ephemeral=private)

tree.add_command(ask, guild=GUILD2)

# ==========================
# /help COMMAND
# ==========================

@tree.command(name="help", description="Show all TankPit Bot commands", guild=GUILD)
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="TankPit Bot Commands", color=0xFF9000)
    embed.add_field(
        name="/award",
        value="Generate a custom award banner.\nExample: `/award tank_name:Grimlock`",
        inline=False,
    )
    embed.add_field(
        name="/tank",
        value="Look up a player profile.\nExample: `/tank tank_name:Frinzee`",
        inline=False,
    )
    embed.add_field(
        name="/leaderboard",
        value="Show the leaderboard.\nExample: `/leaderboard year:2024 top:10`",
        inline=False,
    )
    embed.add_field(
        name="/ask",
        value="Ask the TankPit AI a question.\nExample: `/ask question:What is the Defender of Truth award?`",
        inline=False,
    )
    embed.add_field(
        name="/help",
        value="Show this help message.",
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

tree.add_command(help_command, guild=GUILD2)

# ==========================
# READY + SYNC
# ==========================

@bot.event
async def on_ready():
    for guild_obj in [GUILD, GUILD2]:
        synced = await tree.sync(guild=guild_obj)
        log.info(f"Synced {len(synced)} command(s) to guild {guild_obj.id}")
    log.info(f"Logged in as {bot.user}")

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.exception(f"Unhandled app command error: {error}")
    if not interaction.response.is_done():
        await interaction.response.send_message(f"Unexpected error: `{error}`", ephemeral=True)
    else:
        await interaction.followup.send(f"Unexpected error: `{error}`", ephemeral=True)

print("Bot starting...")
bot.run(TOKEN)