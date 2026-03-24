import asyncio
import json
import logging
import logging.handlers
import os
import hashlib
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
        logging.handlers.RotatingFileHandler(
            "bot.log", maxBytes=5 * 1024 * 1024, backupCount=3
        ),
    ]
)
log = logging.getLogger(__name__)

# ==========================
# ENV
# ==========================

load_dotenv()

TOKEN          = os.getenv("DISCORD_TOKEN")
_GUILD_ID_RAW  = os.getenv("GUILD_ID")
_GUILD_ID_2_RAW = os.getenv("GUILD_ID_2")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN missing")
if not _GUILD_ID_RAW:
    raise ValueError("GUILD_ID missing")
if not _GUILD_ID_2_RAW:
    raise ValueError("GUILD_ID_2 missing")

GUILD_ID  = int(_GUILD_ID_RAW)
GUILD_ID_2 = int(_GUILD_ID_2_RAW)

# ==========================
# CONFIG
# ==========================

SPRITE_PATH = "assets/awards.gif"
FONT_PATH = "fonts/Gamer-Bold.otf"
ICON_HEIGHT = 16
CACHE_FOLDER = "cache"
BIBLE_PATH = os.getenv("BIBLE_PATH", "/home/ukhan/tankpit-ai/bible_chunks.json")
DB_PATH     = os.getenv("DB_PATH",    "/home/ukhan/tankpit-ai/tankpit.db")

os.makedirs(CACHE_FOLDER, exist_ok=True)

# ==========================
# RAG DATA
# ==========================

_RAG_AVAILABLE = False
BIBLE_TEXTS: list = []
BIBLE_EMBEDDINGS_NORM = None

try:
    with open(BIBLE_PATH) as _f:
        _raw_chunks = json.load(_f)
    _valid_texts, _valid_embs = [], []
    for _c in _raw_chunks:
        _e = _c.get("embedding")
        if not isinstance(_e, list) or len(_e) == 0:
            continue
        _arr = np.array(_e, dtype=np.float32)
        if _arr.ndim != 1:
            log.warning("Skipping chunk with unexpected embedding shape %s", _arr.shape)
            continue
        _valid_texts.append(_c["text"])
        _valid_embs.append(_arr)
    if not _valid_embs:
        raise ValueError("No valid embeddings found in bible_chunks.json")
    BIBLE_TEXTS = _valid_texts
    _emb = np.stack(_valid_embs)  # guaranteed 2D: (n_chunks, dim)
    _norms = np.linalg.norm(_emb, axis=1, keepdims=True)
    BIBLE_EMBEDDINGS_NORM = _emb / np.where(_norms == 0, 1, _norms)
    _RAG_AVAILABLE = True
    log.info("RAG loaded: %d chunks", len(BIBLE_TEXTS))
except FileNotFoundError:
    log.warning("bible_chunks.json not found — /ask command will be unavailable")
except Exception as _e:
    log.warning("Failed to load RAG data (%s) — /ask command will be unavailable", _e)

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
# AWARD EMOJI MAP
# ==========================

AWARD_EMOJI = {
    "Single Star":           "<:single_star:1483487155417382913>",
    "Double Star":           "<:double_star:1483486945941262569>",
    "Triple Star":           "<:triple_star:1483487180272701470>",
    "Bronze Tank":           "<:bronze_tank:1483486898113609738>",
    "Silver Tank":           "<:silver_tank:1483487134584410356>",
    "Golden Tank":           "<:golden_tank:1483487004577632286>",
    "Combat Honor":          "<:combat_honor:1483486924311232673>",
    "Combat Honor Medal":    "<:combat_honor:1483486924311232673>",
    "Battle Honor":          "<:battle_honor:1483486861203603476>",
    "Battle Honor Medal":    "<:battle_honor:1483486861203603476>",
    "Heroic Honor":          "<:heroic_honor:1483487022030127238>",
    "Heroic Honor Medal":    "<:heroic_honor:1483487022030127238>",
    "Shining Sword":         "<:shining_sword:1483487096101535945>",
    "Battered Sword":        "<:battered_sword:1483486605850181855>",
    "Rusty Sword":           "<:rusty_sword:1483487077814374533>",
    "Defender of Truth":     "<:defender_truth:1483486967915086005>",
    "Defender of the Truth": "<:defender_truth:1483486967915086005>",
    "Bronze Cup":            "<:bronze_cup:1483486879260213360>",
    "Silver Cup":            "<:silver_cup:1483487114460004412>",
    "Gold Cup":              "<:gold_cup:1483486986118627492>",
    "Purple Heart":          "<:purple_heart1:1483487699951161354>",
    "War Correspondent":     "<:war_correspondent:1483487200405356704>",
    "Lightbulb":             "<:lightbulb:1483487044159148284>",
}

def inject_award_emoji(text: str) -> str:
    import re
    for name in sorted(AWARD_EMOJI, key=len, reverse=True):
        emoji = AWARD_EMOJI[name]
        text = re.sub(re.escape(name), f"{emoji} {name}", text, flags=re.IGNORECASE)
    return text



# ==========================
# SQL QUERY LAYER
# ==========================
import sqlite3 as _sqlite3
import json as _json
_DB_PATH = DB_PATH

_AWARD_KEYS_BY_INDEX = [
    ["single_star","double_star","triple_star"],
    ["bronze_tank","silver_tank","golden_tank"],
    ["combat_honor","battle_honor","heroic_honor"],
    ["shining_sword","battered_sword","rusty_sword"],
    ["defender_truth","defender_truth","defender_truth"],
    ["bronze_cup","silver_cup","gold_cup"],
    ["purple_heart","purple_heart","purple_heart"],
    ["war_correspondent","war_correspondent","war_correspondent"],
    ["lightbulb","lightbulb","lightbulb"],
]

# Snake_case key -> Discord emoji string (mirrors AWARD_EMOJI but keyed by snake_case)
_EMOJI_BY_KEY = {
    "single_star":         "<:single_star:1483487155417382913>",
    "double_star":         "<:double_star:1483486945941262569>",
    "triple_star":         "<:triple_star:1483487180272701470>",
    "bronze_tank":         "<:bronze_tank:1483486898113609738>",
    "silver_tank":         "<:silver_tank:1483487134584410356>",
    "golden_tank":         "<:golden_tank:1483487004577632286>",
    "combat_honor":        "<:combat_honor:1483486924311232673>",
    "battle_honor":        "<:battle_honor:1483486861203603476>",
    "heroic_honor":        "<:heroic_honor:1483487022030127238>",
    "shining_sword":       "<:shining_sword:1483487096101535945>",
    "battered_sword":      "<:battered_sword:1483486605850181855>",
    "rusty_sword":         "<:rusty_sword:1483487077814374533>",
    "defender_truth":      "<:defender_truth:1483486967915086005>",
    "defender_of_truth":   "<:defender_truth:1483486967915086005>",
    "bronze_cup":          "<:bronze_cup:1483486879260213360>",
    "silver_cup":          "<:silver_cup:1483487114460004412>",
    "gold_cup":            "<:gold_cup:1483486986118627492>",
    "purple_heart":        "<:purple_heart1:1483487699951161354>",
    "war_correspondent":   "<:war_correspondent:1483487200405356704>",
    "lightbulb":           "<:lightbulb:1483487044159148284>",
}

_COLOR_DOT = {
    "blue":   "🔵",
    "red":    "🔴",
    "orange": "🟠",
    "purple": "🟣",
}

def _awards_to_emoji(awards_json: str) -> str:
    """Convert awards_json to emoji-only string."""
    if not awards_json or awards_json == "[]":
        return ""
    try:
        awards = _json.loads(awards_json)
        emojis = []
        for i, item in enumerate(awards):
            if isinstance(item, str):
                # Clean format: "Triple Star" -> "triple_star"
                key = item.lower().strip().replace(" ", "_")
                # Normalize variations
                key = key.replace("of_the_truth", "truth").replace("defender_truth", "defender_truth")
                key = key.replace("_medal", "")
                # Direct lookup
                if key in _EMOJI_BY_KEY:
                    emojis.append(_EMOJI_BY_KEY[key])
                else:
                    # Try partial match for edge cases like "defender_of_truth"
                    for k in _EMOJI_BY_KEY:
                        if k in key or key in k:
                            emojis.append(_EMOJI_BY_KEY[k])
                            break
            elif isinstance(item, dict):
                # Raw format: {"name": "3", "tier": "unknown"}
                try:
                    val = int(item.get("name", 0))
                    if val > 0 and i < len(_AWARD_KEYS_BY_INDEX):
                        idx = min(val, 3) - 1
                        if 0 <= idx < len(_AWARD_KEYS_BY_INDEX[i]):
                            key = _AWARD_KEYS_BY_INDEX[i][idx]
                            if key in _EMOJI_BY_KEY:
                                emojis.append(_EMOJI_BY_KEY[key])
                except (ValueError, IndexError):
                    pass
        return " ".join(emojis)
    except Exception:
        return ""

def _profile_link(name: str, tank_id, color: str = "") -> str:
    dot = _COLOR_DOT.get(color, "")
    prefix = f"{dot} " if dot else ""
    if tank_id:
        return f"{prefix}[{name}](https://tankpit.com/tanks/profile?tank_id={tank_id})"
    return f"{prefix}**{name}**"

def _parse_top_n(q: str, default: int = 5) -> int:
    import re
    m = re.search(r"top\s*(\d+)", q)
    if m:
        return min(int(m.group(1)), 100)
    if "top ten" in q or "top 10" in q:
        return 10
    if "top twenty" in q or "top 25" in q or "top twenty five" in q:
        return 25
    if "top hundred" in q or "top 100" in q:
        return 100
    return default

def _db_query(question: str) -> str | None:
    q = question.lower().strip()
    try:
        con = _sqlite3.connect(_DB_PATH)
        con.row_factory = _sqlite3.Row
        cur = con.cursor()

        # --- LEADERBOARD / TOP OVERALL ---
        colors = []
        for c in ["blue","red","orange","purple"]:
            if c in q:
                colors.append(c)
        color_filter = colors[0] if colors else None

        if any(w in q for w in ["top ten overall","top 10 overall","top overall","leaderboard overall","overall leaderboard","who is top","overall ranking","overall rank","top ten","top 10","overall top","top players","leaderboard","who are top","blues","reds","oranges","purples"])  or (any(c in q for c in ["blue","red","orange","purple"]) and any(w in q for w in ["top","leaderboard","best","ranking","rank"])):
            n = _parse_top_n(q, 10)
            if color_filter:
                cur.execute("SELECT name, tank_id, awards_json, leaderboard_rank_overall FROM tanks WHERE leaderboard_rank_overall > 0 AND color=? ORDER BY leaderboard_rank_overall ASC LIMIT ?", (color_filter, n))
            else:
                cur.execute("SELECT name, tank_id, awards_json, leaderboard_rank_overall FROM tanks WHERE leaderboard_rank_overall > 0 ORDER BY leaderboard_rank_overall ASC LIMIT ?", (n,))
            rows = cur.fetchall()
            con.close()
            if rows:
                lines = []
                for i, r in enumerate(rows, 1):
                    emoji = _awards_to_emoji(r["awards_json"])
                    link = _profile_link(r["name"], r["tank_id"], r["color"] or "")
                    overall = f" *(#{r['leaderboard_rank_overall']} overall)*" if color_filter else ""
                    lines.append(f"{i}. {link} {emoji}{overall}")
                title = f"**{color_filter.title()} Overall Leaderboard (Top {n}):**" if color_filter else f"**Overall Leaderboard (Top {n}):**"
                return title + "\n" + "\n".join(lines)

        # --- RANK COUNT ---
        for rank in ["general","colonel","major","captain","lieutenant","sergeant","recruit"]:
            if rank in q and any(w in q for w in ["how many","count","total","number of"]):
                cur.execute("SELECT COUNT(*) as n FROM tanks WHERE rank=?", (rank,))
                n = cur.fetchone()["n"]
                con.close()
                return f"There are **{n}** players with the rank of **{rank}** in the database."

        # --- TOP CUPS ---
        if any(w in q for w in ["most gold cup","most gold cups","top gold cup"]):
            n = _parse_top_n(q, 5)
            cur.execute("SELECT name, tank_id, color, gold_cups, awards_json FROM tanks WHERE gold_cups > 0 AND (bf_tank_name IS NULL OR bf_tank_name = '' OR bf_tank_name = 'Unknown') ORDER BY gold_cups DESC LIMIT ?", (n,))
            rows = cur.fetchall()
            con.close()
            if rows:
                lines = [f"{i+1}. {_profile_link(r['name'],r['tank_id'],r['color'] or '')} {_awards_to_emoji(r['awards_json'])} — **{r['gold_cups']}** gold cups" for i,r in enumerate(rows)]
                return f"**Top {n} by Gold Cups:**\n" + "\n".join(lines)

        if any(w in q for w in ["most silver cup","most silver cups","top silver cup"]):
            n = _parse_top_n(q, 5)
            cur.execute("SELECT name, tank_id, color, silver_cups, awards_json FROM tanks WHERE silver_cups > 0 AND (bf_tank_name IS NULL OR bf_tank_name = '' OR bf_tank_name = 'Unknown') ORDER BY silver_cups DESC LIMIT ?", (n,))
            rows = cur.fetchall()
            con.close()
            if rows:
                lines = [f"{i+1}. {_profile_link(r['name'],r['tank_id'],r['color'] or '')} {_awards_to_emoji(r['awards_json'])} — **{r['silver_cups']}** silver cups" for i,r in enumerate(rows)]
                return f"**Top {n} by Silver Cups:**\n" + "\n".join(lines)

        if any(w in q for w in ["most bronze cup","most bronze cups","top bronze cup"]):
            n = _parse_top_n(q, 5)
            cur.execute("SELECT name, tank_id, color, bronze_cups, awards_json FROM tanks WHERE bronze_cups > 0 AND (bf_tank_name IS NULL OR bf_tank_name = '' OR bf_tank_name = 'Unknown') ORDER BY bronze_cups DESC LIMIT ?", (n,))
            rows = cur.fetchall()
            con.close()
            if rows:
                lines = [f"{i+1}. {_profile_link(r['name'],r['tank_id'],r['color'] or '')} {_awards_to_emoji(r['awards_json'])} — **{r['bronze_cups']}** bronze cups" for i,r in enumerate(rows)]
                return f"**Top {n} by Bronze Cups:**\n" + "\n".join(lines)

        if any(w in q for w in ["most cups","most tournament","most victories","top cups","top tournament"]):
            n = _parse_top_n(q, 5)
            cur.execute("SELECT name, tank_id, color, total_cups, awards_json FROM tanks WHERE total_cups > 0 AND (bf_tank_name IS NULL OR bf_tank_name = '' OR bf_tank_name = 'Unknown') ORDER BY total_cups DESC LIMIT ?", (n,))
            rows = cur.fetchall()
            con.close()
            if rows:
                lines = [f"{i+1}. {_profile_link(r['name'],r['tank_id'],r['color'] or '')} {_awards_to_emoji(r['awards_json'])} — **{r['total_cups']}** total cups" for i,r in enumerate(rows)]
                return f"**Top {n} by Total Tournament Victories:**\n" + "\n".join(lines)

        # --- MOST KILLS ---
        if any(w in q for w in ["most kills","most enemies","highest kills","top kills","most kill"]):
            n = _parse_top_n(q, 5)
            cur.execute("SELECT name, tank_id, color, destroyed_enemies, awards_json FROM tanks WHERE destroyed_enemies > 0 AND (bf_tank_name IS NULL OR bf_tank_name = '' OR bf_tank_name = 'Unknown') ORDER BY destroyed_enemies DESC LIMIT ?", (n,))
            rows = cur.fetchall()
            con.close()
            if rows:
                lines = [f"{i+1}. {_profile_link(r['name'],r['tank_id'],r['color'] or '')} {_awards_to_emoji(r['awards_json'])} — **{r['destroyed_enemies']:,}** kills" for i,r in enumerate(rows)]
                return f"**Top {n} by Kills:**\n" + "\n".join(lines)

        # --- AWARD QUERIES ---
        award_map = {
            "triple star":"Triple Star","double star":"Double Star","single star":"Single Star",
            "golden tank":"Golden Tank","silver tank":"Silver Tank","bronze tank":"Bronze Tank",
            "heroic honor":"Heroic Honor","battle honor":"Battle Honor","combat honor":"Combat Honor",
            "shining sword":"Shining Sword","battered sword":"Battered Sword","rusty sword":"Rusty Sword",
            "defender of truth":"Defender of Truth","gold cup":"Gold Cup","silver cup":"Silver Cup",
            "bronze cup":"Bronze Cup","purple heart":"Purple Heart",
            "war correspondent":"War Correspondent","lightbulb":"Lightbulb",
        }
        for key, display in award_map.items():
            if key in q:
                if any(w in q for w in ["how many","count","total","number"]):
                    cur.execute("SELECT COUNT(*) as n FROM tanks WHERE awards_json LIKE ?", (f"%{display}%",))
                    n = cur.fetchone()["n"]
                    con.close()
                    emoji = AWARD_EMOJI.get(display, "")
                    return f"There are **{n}** players with the {emoji} **{display}** award in the database."
                if any(w in q for w in ["who has","list","show","players with","tanks with","all players","give me"]):
                    top_n = _parse_top_n(q, 10)
                    cur.execute("SELECT name, tank_id, color, awards_json FROM tanks WHERE awards_json LIKE ? ORDER BY name LIMIT ?", (f"%{display}%", top_n))
                    rows = cur.fetchall()
                    con.close()
                    if rows:
                        lines = [f"• {_profile_link(r['name'],r['tank_id'],r['color'] or '')} {_awards_to_emoji(r['awards_json'])}" for r in rows]
                        emoji = AWARD_EMOJI.get(display, "")
                        return f"**Players with {emoji} {display} (showing {len(rows)}):**\n" + "\n".join(lines)

        # --- TOTAL PLAYERS ---
        if any(w in q for w in ["how many players","how many tanks","total players","total tanks"]):
            cur.execute("SELECT COUNT(*) as n FROM tanks")
            n = cur.fetchone()["n"]
            con.close()
            return f"There are **{n}** players in the TankPit database."

        con.close()
        return None

    except Exception as e:
        try:
            con.close()
        except:
            pass
        return None

# ==========================
# PLAYER CARD CONSTANTS
# ==========================

_PC_W        = 500
_PC_BG       = (25,  32,  38)   # #192026
_PC_ACCENT   = (63,  202, 112)  # #3fca70
_PC_ACCENT_W = 4
_PC_PAD      = 20
_PC_WHITE    = (255, 255, 255)
_PC_MUTED    = (128, 157, 177)  # #809db1

_PC_FACTION  = {
    "red":    (224,  0,   0),
    "blue":   (0,    0,  224),
    "orange": (255, 144,  0),
    "purple": (223,  0,  224),
}

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
# PLAYER CARD GENERATOR
# ==========================

def _fmt_stat(val, default="—"):
    return str(val) if val is not None else default


def generate_player_card(profile: dict) -> str:
    tank_id   = profile.get("tank_id")
    # Hash key on stats that change so stale cards are never served
    world = (profile.get("map_data") or {}).get("World") or {}
    _cache_str = f"{tank_id}|{profile.get('name')}|{world.get('rank')}|{world.get('destroyed_enemies')}|{world.get('deactivated')}|{world.get('time_played')}|{profile.get('main_color')}|{profile.get('country')}|{profile.get('favorite_map')}|{profile.get('awards')}"
    cache_key = f"pc_{hashlib.md5(_cache_str.encode()).hexdigest()}"
    cache_path = os.path.join(CACHE_FOLDER, f"{cache_key}.png")
    if os.path.exists(cache_path):
        return cache_path

    name    = profile.get("name") or "Unknown"
    color_k = (profile.get("main_color") or "").lower()
    fav_map = (profile.get("favorite_map") or "—")[:22]
    country = (profile.get("country") or "")[:30]

    world   = (profile.get("map_data") or {}).get("World") or {}
    private = not world
    rank_val   = "Private" if private else _fmt_stat(world.get("rank"), "—").capitalize()
    kills_val  = "Private" if private else _fmt_stat(world.get("destroyed_enemies"))
    deaths_val = "Private" if private else _fmt_stat(world.get("deactivated"))

    tp = world.get("time_played")
    if private:
        time_played = "Private"
    elif isinstance(tp, (int, float)) and tp > 0:
        hours = int(tp) // 60
        mins  = int(tp) % 60
        time_played = f"{hours}h {mins}m" if hours else f"{mins}m"
    elif tp:
        time_played = str(tp)
    else:
        time_played = "—"

    tv = profile.get("user_tournament_victories") or {}
    if not tv:
        tv_lists = profile.get("tournament_victories") or {}
        gold_n   = len(tv_lists.get("gold",   []))
        silver_n = len(tv_lists.get("silver", []))
        bronze_n = len(tv_lists.get("bronze", []))
    else:
        gold_n   = int(tv.get("gold",   0) or 0)
        silver_n = int(tv.get("silver", 0) or 0)
        bronze_n = int(tv.get("bronze", 0) or 0)

    raw_awards = profile.get("awards") or []

    font_name_  = ImageFont.truetype(FONT_PATH, 24)
    font_label  = ImageFont.truetype(FONT_PATH, 11)
    font_val    = ImageFont.truetype(FONT_PATH, 14)
    font_footer = ImageFont.truetype(FONT_PATH, 11)

    sprite = Image.open(SPRITE_PATH).convert("RGBA")

    header_icons = []
    for i, val in enumerate(raw_awards):
        if val and i < len(AWARD_KEYS_BY_INDEX):
            key = AWARD_KEYS_BY_INDEX[i][min(val, 3) - 1]
            header_icons.append(crop_award(sprite, AWARDS[key]["class"]))

    # --- Measure for layout ---
    probe = Image.new("RGBA", (1, 1))
    pd    = ImageDraw.Draw(probe)

    def _th(text, font):
        b = pd.textbbox((0, 0), text, font=font)
        return b[3] - b[1]

    name_h   = _th(name, font_name_)
    label_h  = _th("Rank", font_label)
    val_h    = _th("00000", font_val)
    footer_h = _th("ID: 00000", font_footer)

    header_row_h = max(name_h, ICON_HEIGHT)
    stats_row_h  = label_h + 4 + val_h
    gap = 14

    total_h = _PC_PAD + header_row_h + gap + stats_row_h + gap + stats_row_h + gap + footer_h + _PC_PAD

    # --- Draw ---
    img  = Image.new("RGB", (_PC_W, total_h), _PC_BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, _PC_ACCENT_W - 1, total_h - 1], fill=_PC_ACCENT)

    x0 = _PC_ACCENT_W + _PC_PAD
    y  = _PC_PAD

    # Color dot
    dot_r  = 5
    dot_cx = x0 + dot_r
    dot_cy = y + name_h // 2
    draw.ellipse(
        [dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r],
        fill=_PC_FACTION.get(color_k, _PC_MUTED),
    )

    draw.text((x0 + dot_r * 2 + 6, y), name, fill=_PC_WHITE, font=font_name_)

    # Award icons — right-aligned, vertically centered with name
    ax     = _PC_W - _PC_PAD
    icon_y = y + (name_h - ICON_HEIGHT) // 2
    for icon in reversed(header_icons):
        ax -= icon.width
        img.paste(icon, (ax, max(icon_y, 0)), icon)
        ax -= 2

    y += header_row_h + gap

    col_w = (_PC_W - x0 - _PC_PAD) // 3

    def draw_stat_cell(cx, cy, label, value_text=None, cup_counts=None):
        draw.text((cx, cy), label, fill=_PC_MUTED, font=font_label)
        vy = cy + label_h + 4
        if cup_counts is not None:
            ix  = cx
            has = False
            for cup_key, count in cup_counts:
                if count:
                    has = True
                    icon = crop_award(sprite, AWARDS[cup_key]["class"])
                    img.paste(icon, (ix, vy + (val_h - ICON_HEIGHT) // 2), icon)
                    ix += icon.width + 2
                    cnt = f"×{count}"
                    cb  = pd.textbbox((0, 0), cnt, font=font_label)
                    draw.text(
                        (ix, vy + (val_h - (cb[3] - cb[1])) // 2),
                        cnt, fill=_PC_WHITE, font=font_label,
                    )
                    ix += (cb[2] - cb[0]) + 5
            if not has:
                draw.text((cx, vy), "—", fill=_PC_WHITE, font=font_val)
        else:
            draw.text((cx, vy), value_text, fill=_PC_WHITE, font=font_val)

    # Row 1: Time Played | Rank | Kills
    for ci, (label, value) in enumerate([
        ("Time Played", time_played),
        ("Rank",        rank_val),
        ("Kills",       kills_val),
    ]):
        draw_stat_cell(x0 + ci * col_w, y, label, value_text=value)

    y += stats_row_h + gap

    # Row 2: Deaths | Cups | Favorite Map
    cups = [("gold_cup", gold_n), ("silver_cup", silver_n), ("bronze_cup", bronze_n)]
    draw_stat_cell(x0,            y, "Deaths",       value_text=deaths_val)
    draw_stat_cell(x0 + col_w,   y, "Cups",          cup_counts=cups)
    draw_stat_cell(x0 + 2*col_w, y, "Favorite Map",  value_text=fav_map)

    y += stats_row_h + gap

    # Footer
    if country:
        draw.text((x0, y), country, fill=_PC_MUTED, font=font_footer)
    if tank_id:
        id_text = f"ID: {tank_id}"
        ib  = pd.textbbox((0, 0), id_text, font=font_footer)
        id_w = ib[2] - ib[0]
        draw.text((_PC_W - _PC_PAD - id_w, y), id_text, fill=_PC_MUTED, font=font_footer)

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
            image_path = await asyncio.to_thread(
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

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="Session expired. Run `/award` again.", view=None
                )
            except discord.NotFound:
                pass


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


def build_profile_link_embed(profile: dict) -> discord.Embed:
    tank_id    = profile.get("tank_id")
    color_name = (profile.get("main_color") or "").lower()
    color      = {"blue": 0x0000E0, "red": 0xE00000, "orange": 0xFF9000, "purple": 0xDF00E0}.get(color_name, 0x3FCA70)
    name       = profile.get("name", "Unknown")
    url        = f"https://tankpit.com/tanks/profile?tank_id={tank_id}" if tank_id else "https://tankpit.com"
    return discord.Embed(description=f"[View {name}'s profile on TankPit]({url})", color=color)


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
            profile    = await fetch_tank_profile(tank_id)
            image_path = await asyncio.to_thread(generate_player_card, profile)
        except Exception as e:
            log.exception(f"TankSelectView profile fetch failed (id={tank_id}): {e}")
            await interaction.edit_original_response(content=f"Failed to load profile: `{e}`", embed=None, view=None)
            return
        embed = build_profile_link_embed(profile)
        await interaction.edit_original_response(
            content=None,
            attachments=[discord.File(image_path)],
            embed=embed,
            view=None,
        )


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
    image_path = await asyncio.to_thread(generate_player_card, profile)
    embed = build_profile_link_embed(profile)
    await interaction.edit_original_response(
        content=None,
        attachments=[discord.File(image_path)],
        embed=embed,
    )

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


async def fetch_leaderboard(
    year: str = "overall",
    page: int = 1,
    color: str = None,
    rank: str = None,
) -> dict:
    params: dict = {"leaderboard": year, "page": page}
    if color:
        params["color"] = color
    if rank:
        params["rank"] = rank
    async with aiohttp.ClientSession() as session:
        async with session.get(
            LEADERBOARD_URL,
            params=params,
            timeout=_API_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


@tree.command(name="leaderboard", description="Show the TankPit leaderboard", guild=GUILD)
@app_commands.describe(
    year="Year (e.g. 2024) or 'overall' (default)",
    top="How many to show (default 10, max 100)",
    color="Filter by faction color",
    rank="Filter by rank",
)
@app_commands.choices(
    color=[
        app_commands.Choice(name="Red",    value="red"),
        app_commands.Choice(name="Purple", value="purple"),
        app_commands.Choice(name="Blue",   value="blue"),
        app_commands.Choice(name="Orange", value="orange"),
    ],
    rank=[
        app_commands.Choice(name="General",    value="general"),
        app_commands.Choice(name="Colonel",    value="colonel"),
        app_commands.Choice(name="Major",      value="major"),
        app_commands.Choice(name="Captain",    value="captain"),
        app_commands.Choice(name="Lieutenant", value="lieutenant"),
        app_commands.Choice(name="Sergeant",   value="sergeant"),
        app_commands.Choice(name="Corporal",   value="corporal"),
        app_commands.Choice(name="Private",    value="private"),
        app_commands.Choice(name="Recruit",    value="recruit"),
    ],
)
async def leaderboard(
    interaction: discord.Interaction,
    year: str = "overall",
    top: int = 10,
    color: str = None,
    rank: str = None,
):
    top = max(1, min(top, 100))
    await interaction.response.defer()
    try:
        data = await fetch_leaderboard(year=year, color=color, rank=rank)
    except aiohttp.ClientResponseError as e:
        await interaction.followup.send(f"API error: `{e.status} {e.message}`")
        return
    except Exception as e:
        log.exception(f"/leaderboard failed: {e}")
        await interaction.followup.send(f"Failed to reach TankPit API: `{e}`")
        return

    results = data.get("results", [])[:top]
    if not results:
        filter_note = " with these filters" if (color or rank) else ""
        await interaction.followup.send(f"No leaderboard data for **{year}**{filter_note}.")
        return

    # Build title — show active filters when present
    filter_parts = []
    if color:
        filter_parts.append(color.capitalize())
    if rank:
        filter_parts.append(rank.capitalize() + "s")
    if filter_parts:
        title = f"{year.capitalize()} Rankings — {' '.join(filter_parts)}"
    else:
        title = f"TankPit Leaderboard — {year.capitalize()}"

    total_pages = data.get("total_pages", 1)

    image_path = await asyncio.to_thread(generate_leaderboard_image, results, title, 1, total_pages)

    # Small embed with top-3 clickable names
    embed = discord.Embed(color=0xFF9000)
    top3_lines = []
    for entry in results[:3]:
        placing  = entry.get("placing")
        name     = entry.get("name", "Unknown")
        tank_id  = entry.get("tank_id")
        url      = f"https://tankpit.com/tanks/profile?tank_id={tank_id}" if tank_id else "https://tankpit.com"
        medal    = {1: "🥇", 2: "🥈", 3: "🥉"}.get(placing, "")
        top3_lines.append(f"{medal} [{name}]({url})")
    embed.description = "\n".join(top3_lines)

    footer_parts = [f"year:{year}", f"top:{top}"]
    if color:
        footer_parts.append(f"color:{color}")
    if rank:
        footer_parts.append(f"rank:{rank}")
    embed.set_footer(text=f"Page 1 of {total_pages} • /leaderboard {' '.join(footer_parts)}")

    await interaction.followup.send(file=discord.File(image_path), embed=embed)
    log.info(f"/leaderboard: year={year} top={top} color={color} rank={rank}")

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

    if not _RAG_AVAILABLE:
        await interaction.followup.send(
            "The `/ask` command is not available on this deployment.", ephemeral=True
        )
        return

    # In-memory cache check
    cached = _ASK_CACHE.get(question)
    if cached and time.time() < cached[1]:
        answer = cached[0]
        log.info(f"/ask (cached): q={question!r}")
    else:
        # Try SQL layer first, fall back to RAG
        db_answer = await asyncio.to_thread(_db_query, question)
        if db_answer is not None:
            answer = db_answer
            _ASK_CACHE[question] = (answer, time.time() + _ask_ttl(question))
            if len(answer) > 4096:
                answer = answer[:4093] + "…"
            embed = discord.Embed(title=question[:256], description=answer, color=0xFF9000)
            embed.set_author(name=interaction.user.display_name, icon_url=str(interaction.user.display_avatar.url))
            await interaction.followup.send(embed=embed, ephemeral=private)
            return
        try:
            answer = await asyncio.to_thread(_rag_query, question)
        except Exception as e:
            log.exception(f"/ask failed for '{question}': {e}")
            await interaction.followup.send(f"Error querying AI: `{e}`", ephemeral=True)
            return
        _ASK_CACHE[question] = (answer, time.time() + _ask_ttl(question))

    if len(answer) > 4096:
        answer = answer[:4093] + "…"
    answer = inject_award_emoji(answer)

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

log.info("Bot starting...")
bot.run(TOKEN)