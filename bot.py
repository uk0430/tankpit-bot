import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
import os
import hashlib
from dotenv import load_dotenv

# ==========================
# LOAD ENV VARIABLES
# ==========================

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError("No DISCORD_TOKEN found in environment variables.")

# ==========================
# CONFIG
# ==========================

GUILD_ID = 615551999701811221  # <-- Your server ID

SPRITE_PATH = "assets/awards.gif"
FONT_PATH = "fonts/Gamer-Bold.otf"
ICON_HEIGHT = 16

CACHE_FOLDER = "cache"
if not os.path.exists(CACHE_FOLDER):
    os.makedirs(CACHE_FOLDER)

# ==========================
# OFFICIAL COLORS
# ==========================

OFFICIAL_COLORS = {
    "Orange": (255, 144, 0),
    "Purple": (223, 0, 224),
    "Blue": (0, 0, 224),
    "Red": (224, 0, 0),
}

TANKPIT_BG = (255, 255, 224)
TANKPIT_TEXT = (255, 144, 0)

SIZE_OPTIONS = {
    "Default": 1.0,
    "Medium": 1.3,
    "Large": 1.6,
}

SPRITE_DATA = {
    "a0-1": {"x": 13, "w": 13},
    "a0-2": {"x": 26, "w": 13},
    "a0-3": {"x": 39, "w": 13},
    "a1-1": {"x": 82, "w": 30},
    "a1-2": {"x": 112, "w": 30},
    "a1-3": {"x": 142, "w": 30},
}

AWARDS = {
    "single_star": {"class": "a0-1", "display": "Single Star"},
    "double_star": {"class": "a0-2", "display": "Double Star"},
    "triple_star": {"class": "a0-3", "display": "Triple Star"},
    "bronze_tank": {"class": "a1-1", "display": "Bronze Tank"},
    "silver_tank": {"class": "a1-2", "display": "Silver Tank"},
    "golden_tank": {"class": "a1-3", "display": "Golden Tank"},
}

CATEGORY_ORDER = ["single_star","double_star","triple_star","bronze_tank","silver_tank","golden_tank"]

# ==========================
# HELPERS
# ==========================

def crop_award(sprite, class_name):
    data = SPRITE_DATA[class_name]
    return sprite.crop((data["x"], 0, data["x"] + data["w"], ICON_HEIGHT))

def generate_award_banner(name, award_keys, color, banner=False, size_mode="Default"):
    scale = SIZE_OPTIONS[size_mode]

    cache_string = f"{name}_{award_keys}_{color}_{banner}_{size_mode}"
    cache_hash = hashlib.md5(cache_string.encode()).hexdigest()
    cache_path = os.path.join(CACHE_FOLDER, f"{cache_hash}.png")

    if os.path.exists(cache_path):
        return cache_path

    sprite = Image.open(SPRITE_PATH).convert("RGBA")
    font = ImageFont.truetype(FONT_PATH, int(18 * scale))

    padding_x = int(14 * scale)
    padding_y = int(6 * scale)
    spacing = int(4 * scale)

    icons = []
    for key in award_keys:
        icon = crop_award(sprite, AWARDS[key]["class"])
        w,h = icon.size
        icon = icon.resize((int(w*scale), int(h*scale)), Image.NEAREST)
        icons.append(icon)

    awards_width = sum(icon.width for icon in icons)
    awards_width += spacing*(len(icons)-1) if icons else 0

    text_width, text_height = font.getbbox(name)[2:4]

    width = max(text_width, awards_width) + padding_x*2
    height = padding_y*2 + text_height + (icons[0].height if icons else 0)

    img = Image.new("RGBA",(width,height),(0,0,0,0))
    draw = ImageDraw.Draw(img)
    draw.text(((width-text_width)//2,padding_y), name, fill=color, font=font)

    x = (width-awards_width)//2
    y = padding_y+text_height

    for icon in icons:
        img.paste(icon,(x,y),icon)
        x += icon.width+spacing

    img.save(cache_path)
    return cache_path

# ==========================
# DISCORD BOT
# ==========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

class AwardView(discord.ui.View):
    def __init__(self, tank_name):
        super().__init__(timeout=300)
        self.tank_name = tank_name
        self.selected_awards = []
        self.name_color = "Blue"

    @discord.ui.select(
        placeholder="Select awards...",
        min_values=0,
        max_values=len(AWARDS),
        options=[
            discord.SelectOption(label=data["display"], value=key)
            for key,data in AWARDS.items()
        ],
    )
    async def select_awards(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_awards = select.values
        await interaction.response.defer()

    @discord.ui.button(label="Generate", style=discord.ButtonStyle.green)
    async def generate(self, interaction: discord.Interaction, button: discord.ui.Button):
        image_path = generate_award_banner(
            self.tank_name,
            self.selected_awards,
            OFFICIAL_COLORS[self.name_color]
        )
        await interaction.response.send_message(file=discord.File(image_path))

@tree.command(
    name="award",
    description="Generate TankPit awards banner",
    guild=discord.Object(id=GUILD_ID)
)
async def award(interaction: discord.Interaction, tank_name: str):
    view = AwardView(tank_name)
    await interaction.response.send_message(
        f"Customize awards for **{tank_name}**:",
        view=view
    )

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)