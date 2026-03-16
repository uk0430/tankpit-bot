# TankPit Bot — Project Context for Claude

## What This Bot Does

**TankPit Bot** is a Discord bot for the TankPit gaming community. Its core function is generating custom **award/achievement banners** as images that members can share. A user runs `/award <tank_name>`, selects awards, a color, and a size through a dropdown UI, and the bot renders a styled PNG banner combining the tank/player name with award icons.

It is deployed on **Railway.app** (US East Virginia region) and runs in two Discord guilds:
- Production guild: `311890399767822359`
- Test guild: `615551999701811221`

---

## What's Been Built

### Single Command: `/award <tank_name>`

An interactive slash command with a multi-step UI:
1. User types a tank/player name
2. Bot presents three dropdowns: award selection, color, size
3. User hits "Generate Banner" → bot renders and sends the image
4. "Change Name" button opens a modal to edit the name without restarting

### Award System (20 awards in 6 categories)

| Category | Awards |
|----------|--------|
| Stars | Single, Double, Triple |
| Tanks | Bronze, Silver, Golden |
| Medals | Combat Honor, Battle Honor, Heroic Honor |
| Swords | Shining, Battered, Rusty |
| Special | Defender of Truth, Purple Heart, War Correspondent, Lightbulb |
| Cups | Bronze, Silver, Gold |

Award icons are extracted from `assets/awards.gif` (sprite sheet).

### Banner Generation

- Custom font: `fonts/Gamer-Bold.otf`
- Text colors: Orange, Purple, Blue, Red
- Size scaling: Default (1.0×), Medium (1.3×), Large (1.6×)
- MD5-based image cache in `cache/` — avoids re-rendering identical banners
- Cache key: `(name, awards, color, banner_mode, size)`

### UI Architecture

- `AwardSelectionView` — persistent Discord View with dropdowns + buttons, 5-minute timeout
- `ChangeNameModal` — Discord Modal for inline name editing
- All responses are ephemeral (private to the user who ran the command)

---

## What's Working

- `/award` command fully functional end-to-end
- Banner image generation with PIL (Pillow)
- Award sprite extraction and ordering
- Multi-select dropdowns with state persistence
- Image cache (82 images cached currently)
- Railway deployment with auto-restart on failure
- Logging to both console and `bot.log`
- Commands synced to both guilds on startup

### Known Issue

Occasional **"Unknown Interaction" (404)** errors. Discord requires a response within 3 seconds. Recent fix: use `send_message` directly instead of deferring. Still occasionally flaky under load or slow image generation.

---

## Railway / Local Setup

### Railway (Production)

- Config: `railway.toml` — builder: nixpacks, start: `python bot.py`, restart: always
- Also has `Procfile`: `worker: python bot.py`
- Region: US East Virginia
- Env vars set in Railway dashboard (do NOT commit `.env` to git):
  - `DISCORD_TOKEN`
  - `GUILD_ID` (test guild)
  - `GUILD_ID_2` (production guild)

### Local Development

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
python bot.py
```

`.env` file (gitignored) must contain:
```
DISCORD_TOKEN=your_token_here
GUILD_ID=615551999701811221
GUILD_ID_2=311890399767822359
```

### Dependencies

| Package | Purpose |
|---------|---------|
| discord.py 2.6.4 | Discord API |
| Pillow 12.1.1 | Image generation |
| python-dotenv | Env var loading |
| beautifulsoup4, lxml, requests | Legacy / future web scraping |
| numpy | Unused (legacy) |

---

## TankPit APIs — Planned Integrations

The current bot has **no live API integrations** — it is a standalone image generator. However, the dependencies `beautifulsoup4`, `lxml`, and `requests` are already installed (from earlier scraping work) and `tankpit.db` (SQLite), `seen_posts.json`, and `tank_cache.pkl` are leftover artifacts from prior integration attempts.

Planned integrations (to be built):
- **[ ] TBD** — fetch live player/tank stats from TankPit
- **[ ] TBD** — look up award history per player
- **[ ] TBD** — auto-post notifications when new awards/posts appear (the `seen_posts.json` pattern suggests this was attempted before)

> When these are scoped, document the API endpoints and auth method here.

---

## File Structure

```
tankpit-bot-legacy/
├── bot.py               # Entire bot — 372 lines, single-file
├── requirements.txt
├── railway.toml         # Railway deployment config
├── Procfile             # Fallback start command
├── .env                 # Local secrets (gitignored)
├── assets/
│   └── awards.gif       # Sprite sheet — all 20 award icons
├── fonts/
│   └── Gamer-Bold.otf   # Display font for banners
├── cache/               # MD5-named PNG/GIF cache files
├── tankpit.db           # SQLite DB (legacy, unused)
├── tank_cache.pkl        # Pickle cache (legacy, unused)
├── seen_posts.json      # Post tracking (legacy, unused)
└── bot.log              # Live log file
```

---

## Next Steps

1. **Fix interaction timeout reliability** — The 3-second Discord window is tight for PIL rendering. Consider pre-generating or moving render to a thread pool (`asyncio.to_thread`).
2. **Scope TankPit API integrations** — Decide which endpoints to hit, what data to surface, and whether to use polling or webhooks for notifications.
3. **Wire up `tankpit.db`** — Either use it for real (player records, award history) or delete it to avoid confusion.
4. **Clean up legacy deps** — Remove `numpy`, prune `beautifulsoup4`/`lxml`/`requests` if scraping is not going to be used.
5. **Add a `/help` or `/info` command** — Currently no way for users to discover what awards exist.
6. **Consider splitting `bot.py`** — Once API integrations land, the file will grow. Split into `bot.py`, `banner.py`, `tankpit_api.py`.
