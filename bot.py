import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
import os
import hashlib
from dotenv import load_dotenv

# ==========================
# ENV
# ==========================

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError("No DISCORD_TOKEN found in environment variables.")

GUILD_ID = 615551999701811221

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
    "single_star": {"display": "Single Star", "class": "a0-1", "category": "stars"},
    "double_star": {"display": "Double Star", "class": "a0-2", "category": "stars"},
    "triple_star": {"display": "Triple Star", "class": "a0-3", "category": "stars"},
    "bronze_tank": {"display": "Bronze Tank", "class": "a1-1", "category": "tanks"},
    "silver_tank": {"display": "Silver Tank", "class": "a1-2", "category": "tanks"},
    "golden_tank": {"display": "Golden Tank", "class": "a1-3", "category": "tanks"},
    "combat_honor": {"display": "Combat Honor Medal", "class": "a2-1", "category": "medals"},
    "battle_honor": {"display": "Battle Honor Medal", "class": "a2-2", "category": "medals"},
    "heroic_honor": {"display": "Heroic Honor Medal", "class": "a2-3", "category": "medals"},
    "shining_sword": {"display": "Shining Sword", "class": "a3-1", "category": "swords"},
    "battered_sword": {"display": "Battered Sword", "class": "a3-2", "category": "swords"},
    "rusty_sword": {"display": "Rusty Sword", "class": "a3-3", "category": "swords"},
    "defender_truth": {"display": "Defender of the Truth", "class": "a4-3", "category": "special"},
    "bronze_cup": {"display": "Bronze Cup", "class": "a5-1", "category": "cups"},
    "silver_cup": {"display": "Silver Cup", "class": "a5-2", "category": "cups"},
    "gold_cup": {"display": "Gold Cup", "class": "a5-3", "category": "cups"},
    "purple_heart": {"display": "Purple Heart", "class": "a6-1", "category": "other"},
    "war_correspondent": {"display": "War Correspondent", "class": "a7-1", "category": "other"},
    "lightbulb": {"display": "Lightbulb", "class": "a8-1", "category": "other"},
}

CATEGORY_ORDER = ["stars", "tanks", "medals", "swords", "special", "cups", "other"]

# ==========================
# HELPERS
# ==========================

def sort_awards(selected):
    ordered = []
    for category in CATEGORY_ORDER:
        for key, data in AWARDS.items():
            if data["category"] == category and key in selected:
                ordered.append(key)
    return ordered

def crop_award(sprite, class_name):
    data = SPRITE_DATA[class_name]
    return sprite.crop((data["x"], 0, data["x"] + data["w"], ICON_HEIGHT))

def generate_award_banner(name, award_keys, color):
    award_keys = sort_awards(award_keys)

    cache_string = f"{name}_{award_keys}_{color}"
    cache_hash = hashlib.md5(cache_string.encode()).hexdigest()
    cache_path = os.path.join(CACHE_FOLDER, f"{cache_hash}.png")

    if os.path.exists(cache_path):
        return cache_path

    sprite = Image.open(SPRITE_PATH).convert("RGBA")
    font = ImageFont.truetype(FONT_PATH, 18)

    padding = 10
    spacing = 3

    temp = Image.new("RGBA",(1,1))
    draw = ImageDraw.Draw(temp)
    bbox = draw.textbbox((0,0), name, font=font)
    text_width = bbox[2]-bbox[0]
    text_height = bbox[3]-bbox[1]

    icons = [crop_award(sprite, AWARDS[key]["class"]) for key in award_keys]

    awards_width = sum(icon.width for icon in icons)
    awards_width += spacing*(len(icons)-1) if icons else 0

    width = max(text_width, awards_width) + padding*2
    height = padding*2 + text_height + (icons[0].height if icons else 0)

    img = Image.new("RGBA",(width,height),(0,0,0,0))
    draw = ImageDraw.Draw(img)
    draw.text(((width-text_width)//2,padding), name, fill=color, font=font)

    x = (width-awards_width)//2
    y = padding + text_height

    for icon in icons:
        img.paste(icon,(x,y),icon)
        x += icon.width+spacing

    img.save(cache_path)
    return cache_path

# ==========================
# DISCORD
# ==========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

class AwardView(discord.ui.View):
    def __init__(self, tank_name):
        super().__init__(timeout=300)
        self.tank_name = tank_name
        self.selected_awards = []
        self.name_color = "Blue"

        # Award selector
        self.add_item(discord.ui.Select(
            placeholder="Select awards...",
            min_values=0,
            max_values=len(AWARDS),
            options=[
                discord.SelectOption(label=data["display"], value=key)
                for key, data in AWARDS.items()
            ],
            custom_id="award_select"
        ))

        # Color selector
        self.add_item(discord.ui.Select(
            placeholder="Select name color...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=color, value=color)
                for color in OFFICIAL_COLORS.keys()
            ],
            custom_id="color_select"
        ))

    async def interaction_check(self, interaction: discord.Interaction):
        return True

    @discord.ui.select(custom_id="award_select")
    async def award_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_awards = select.values
        await interaction.response.defer()

    @discord.ui.select(custom_id="color_select")
    async def color_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.name_color = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="Generate", style=discord.ButtonStyle.green)
    async def generate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        image_path = generate_award_banner(
            self.tank_name,
            self.selected_awards,
            OFFICIAL_COLORS[self.name_color]
        )

        await interaction.followup.send(file=discord.File(image_path))

@tree.command(
    name="award",
    description="Generate TankPit awards banner",
    guild=discord.Object(id=GUILD_ID)
)
async def award(interaction: discord.Interaction, tank_name: str):
    await interaction.response.defer()
    view = AwardView(tank_name)
    await interaction.followup.send(
        f"Customize awards for **{tank_name}**:",
        view=view
    )

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Logged in as {bot.user}")
    print(f"Total awards loaded: {len(AWARDS)}")

bot.run(TOKEN)