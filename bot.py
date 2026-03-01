import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

# ================= CONFIG =================

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

SPRITE_PATH = "assets/awards.gif"
FONT_PATH = "fonts/Gamer-Bold.otf"
CACHE_DIR = "cache"

os.makedirs(CACHE_DIR, exist_ok=True)

# ================= VALIDATION =================

if not TOKEN:
    raise ValueError("DISCORD_TOKEN missing")

if not os.path.exists(SPRITE_PATH):
    raise FileNotFoundError("assets/awards.gif not found")

if not os.path.exists(FONT_PATH):
    raise FileNotFoundError("fonts/Gamer-Bold.otf not found")

# ================= BOT SETUP =================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

SPRITE = Image.open(SPRITE_PATH).convert("RGBA")
FONT = ImageFont.truetype(FONT_PATH, 32)

# ================= DATA =================

AWARDS = {
    "MVP": (0, 0, 64, 64),
    "Sharpshooter": (64, 0, 128, 64),
    "Champion": (128, 0, 192, 64),
}

COLORS = {
    "Orange": (255, 165, 0),
    "Purple": (128, 0, 128),
    "Blue": (0, 102, 255),
    "Red": (220, 20, 60),
}

SIZES = {
    "Default": 1,
    "Medium": 1.4,
    "Large": 1.8,
}

# ================= RENDER =================

def render_preview(username, award, color, size, banner):
    coords = AWARDS[award]
    award_img = SPRITE.crop(coords)

    scale = SIZES[size]
    new_size = (int(award_img.width * scale), int(award_img.height * scale))
    award_img = award_img.resize(new_size, Image.NEAREST)

    width = max(award_img.width, 400)
    height = award_img.height + 140

    bg_color = (255, 255, 224) if banner else (0, 0, 0)
    img = Image.new("RGBA", (width, height), bg_color)

    draw = ImageDraw.Draw(img)

    text_width = draw.textlength(username, font=FONT)
    draw.text(
        ((width - text_width) / 2, 20),
        username,
        fill=COLORS[color],
        font=FONT
    )

    img.paste(
        award_img,
        ((width - award_img.width) // 2, 70),
        award_img
    )

    return img

# ================= VIEW =================

class AwardView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=180)
        self.user = user
        self.selected_award = list(AWARDS.keys())[0]
        self.selected_color = list(COLORS.keys())[0]
        self.selected_size = "Default"
        self.banner = False

    async def update_preview(self, interaction):
        img = render_preview(
            self.user.display_name,
            self.selected_award,
            self.selected_color,
            self.selected_size,
            self.banner
        )

        path = os.path.join(CACHE_DIR, "preview.png")
        img.save(path)

        await interaction.response.edit_message(
            attachments=[discord.File(path)],
            view=self
        )

    @discord.ui.select(
        placeholder="Select Award",
        options=[discord.SelectOption(label=name) for name in AWARDS.keys()]
    )
    async def award_select(self, interaction: discord.Interaction, select):
        self.selected_award = select.values[0]
        await self.update_preview(interaction)

    @discord.ui.button(label="Orange", style=discord.ButtonStyle.primary)
    async def orange(self, interaction: discord.Interaction, button):
        self.selected_color = "Orange"
        await self.update_preview(interaction)

    @discord.ui.button(label="Purple", style=discord.ButtonStyle.primary)
    async def purple(self, interaction: discord.Interaction, button):
        self.selected_color = "Purple"
        await self.update_preview(interaction)

    @discord.ui.button(label="Blue", style=discord.ButtonStyle.primary)
    async def blue(self, interaction: discord.Interaction, button):
        self.selected_color = "Blue"
        await self.update_preview(interaction)

    @discord.ui.button(label="Red", style=discord.ButtonStyle.primary)
    async def red(self, interaction: discord.Interaction, button):
        self.selected_color = "Red"
        await self.update_preview(interaction)

    @discord.ui.button(label="Toggle Banner", style=discord.ButtonStyle.secondary)
    async def toggle_banner(self, interaction: discord.Interaction, button):
        self.banner = not self.banner
        await self.update_preview(interaction)

    @discord.ui.select(
        placeholder="Select Size",
        row=2,
        options=[discord.SelectOption(label=name) for name in SIZES.keys()]
    )
    async def size_select(self, interaction: discord.Interaction, select):
        self.selected_size = select.values[0]
        await self.update_preview(interaction)

# ================= COMMAND =================

@tree.command(name="award", description="Open award generator")
async def award(interaction: discord.Interaction):
    view = AwardView(interaction.user)

    img = render_preview(
        interaction.user.display_name,
        view.selected_award,
        view.selected_color,
        view.selected_size,
        view.banner
    )

    path = os.path.join(CACHE_DIR, "preview.png")
    img.save(path)

    await interaction.response.send_message(
        file=discord.File(path),
        view=view
    )

# ================= RESET SYNC =================

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)

    await tree.sync(guild=guild)

    print("Synced clean award command to guild.")
    print(f"Logged in as {bot.user}")

# ================= RUN =================

bot.run(TOKEN)