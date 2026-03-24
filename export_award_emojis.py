from pathlib import Path
from PIL import Image

SPRITE_PATH = "assets/awards.gif"
ICON_HEIGHT = 16
OUTPUT_DIR = Path("emoji_exports")
EMOJI_SIZE = 128

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

AWARDS = {
    "single_star":       {"class": "a0-1", "display": "Single Star"},
    "double_star":       {"class": "a0-2", "display": "Double Star"},
    "triple_star":       {"class": "a0-3", "display": "Triple Star"},
    "bronze_tank":       {"class": "a1-1", "display": "Bronze Tank"},
    "silver_tank":       {"class": "a1-2", "display": "Silver Tank"},
    "golden_tank":       {"class": "a1-3", "display": "Golden Tank"},
    "combat_honor":      {"class": "a2-1", "display": "Combat Honor"},
    "battle_honor":      {"class": "a2-2", "display": "Battle Honor"},
    "heroic_honor":      {"class": "a2-3", "display": "Heroic Honor"},
    "shining_sword":     {"class": "a3-1", "display": "Shining Sword"},
    "battered_sword":    {"class": "a3-2", "display": "Battered Sword"},
    "rusty_sword":       {"class": "a3-3", "display": "Rusty Sword"},
    "defender_truth":    {"class": "a4-3", "display": "Defender of Truth"},
    "bronze_cup":        {"class": "a5-1", "display": "Bronze Cup"},
    "silver_cup":        {"class": "a5-2", "display": "Silver Cup"},
    "gold_cup":          {"class": "a5-3", "display": "Gold Cup"},
    "purple_heart":      {"class": "a6-1", "display": "Purple Heart"},
    "war_correspondent": {"class": "a7-1", "display": "War Correspondent"},
    "lightbulb":         {"class": "a8-1", "display": "Lightbulb"},
}

OUTPUT_DIR.mkdir(exist_ok=True)
sprite = Image.open(SPRITE_PATH).convert("RGBA")
print(f"Sprite sheet: {sprite.size}")
for key, info in AWARDS.items():
    data = SPRITE_DATA[info["class"]]
    icon = sprite.crop((data["x"], 0, data["x"] + data["w"], ICON_HEIGHT))
    icon = icon.resize((EMOJI_SIZE, EMOJI_SIZE), Image.NEAREST)
    icon.save(OUTPUT_DIR / f"{key}.png", "PNG")
    print(f"  done {key}.png")
print(f"Done - {len(AWARDS)} PNGs in emoji_exports/")
