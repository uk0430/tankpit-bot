import os
import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
import asyncio
import uuid

# ================= CONFIG =================

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

SPRITE_PATH = "assets/awards.gif"
FONT_PATH = "fonts/Gamer-Bold.otf"

if not TOKEN:
    raise ValueError("DISCORD_TOKEN missing")

# ================= BOT =================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ================= LOAD ASSETS =================

SPRITE = Image.open(SPRITE_PATH).convert("RGBA")
FONT = ImageFont.truetype(FONT_PATH, 32)

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
    award_img = award_img.resize(
        (int(award_img.width * scale), int(award_img.height * scale)),
        Image.NEAREST
    )

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
        self.award = list(AWARDS.keys())[0]
        self.color = list(COLORS.keys())[0]
        self.size = "Default"
        self.banner = False

    async def update_preview(self, interaction):
        img = render_preview(
            self.user.display_name,
            self.award,
            self.color,
            self.size,
            self.banner
        )

        filename = f"preview_{uuid.uuid4().hex}.png"
        img.save(filename)

        await interaction.response.edit_message(
            attachments=[discord.File(filename)],
            view=self
        )

        os.remove(filename)

    @discord.ui.select(
        placeholder="Select Award",
        options=[discord.SelectOption(label=name) for name in AWARDS]
    )
    async def award_select(self, interaction, select):
        self.award = select.values[0]
        await self.update_preview(interaction)

    @discord.ui.button(label="Orange", style=discord.ButtonStyle.primary)
    async def orange(self, interaction, button):
        self.color = "Orange"
        await self.update_preview(interaction)

    @discord.ui.button(label="Purple", style=discord.ButtonStyle.primary)
    async def purple(self, interaction, button):
        self.color = "Purple"
        await self.update_preview(interaction)

    @discord.ui.button(label="Blue", style=discord.ButtonStyle.primary)
    async def blue(self, interaction, button):
        self.color = "Blue"
        await self.update_preview(interaction)

    @discord.ui.button(label="Red", style=discord.ButtonStyle.primary)
    async def red(self, interaction, button):
        self.color = "Red"
        await self.update_preview(interaction)

    @discord.ui.button(label="Toggle Banner", style=discord.ButtonStyle.secondary)
    async def toggle_banner(self, interaction, button):
        self.banner = not self.banner
        await self.update_preview(interaction)

    @discord.ui.select(
        placeholder="Select Size",
        row=2,
        options=[discord.SelectOption(label=name) for name in SIZES]
    )
    async def size_select(self, interaction, select):
        self.size = select.values[0]
        await self.update_preview(interaction)

# ================= COMMAND =================

@tree.command(name="award", description="Open award generator")
async def award(interaction: discord.Interaction):
    view = AwardView(interaction.user)

    img = render_preview(
        interaction.user.display_name,
        view.award,
        view.color,
        view.size,
        view.banner
    )

    filename = f"preview_{uuid.uuid4().hex}.png"
    img.save(filename)

    await interaction.response.send_message(
        file=discord.File(filename),
        view=view
    )

    os.remove(filename)

# ================= SYNC =================

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    print("Award command synced.")
    print(f"Logged in as {bot.user}")

print("Bot starting...")
bot.run(TOKEN)

print("Bot starting...")

try:
    bot.run(TOKEN)
except Exception as e:
    print("Bot crashed:", e)

print("BOT.RUN RETURNED — PROCESS EXITING")