# TankPit Bot — Project Context

> Full master context: `~/.claude/CLAUDE.md`

**Bot file:** `bot.py` (1,467 lines, single file)
**Deploy:** Railway (US East Virginia) — `railway.toml`, nixpacks, `python bot.py`
**Local start:** `tankpit` alias → `~/start-tankpit.sh`

## Commands
- `/award <tank>` — custom award banner PNG (PIL, `send_message` not defer)
- `/tank <tank>` — live player card PNG (TankPit API + cache)
- `/leaderboard [year] [top] [color] [rank]` — leaderboard PNG + embed
- `/ask <question>` — RAG + SQL hybrid; **disabled on Railway** (llama.cpp local only)
- `/help` — ephemeral command list

## Architecture
- **Image gen:** PIL in `asyncio.to_thread`, MD5-keyed PNG cache in `cache/`
- **SQL layer (`_db_query`):** SQLite at `~/tankpit-ai/tankpit.db`, 13,250 players
- **RAG layer (`_rag_query`):** nomic-embed (8081) → cosine search → Mistral (8080)
- **RAG data:** `~/tankpit-ai/bible_chunks.json` (13,250 chunks, rebuilt 2026-03-17)
- **Awards:** 19 awards, sprite from `assets/awards.gif`, Discord custom emoji in both guilds

## TankPit API
- `GET https://tankpit.com/api/find_tank?name=<name>`
- `GET https://tankpit.com/api/tank?tank_id=<id>`
- `GET https://tankpit.com/api/leaderboards?leaderboard=<year>&page=<n>&color=<c>&rank=<r>`

## DB Schema (`tanks` table)
`tank_id, name, rank, color, country, time_played, destroyed_enemies, deactivated,`
`cups_{gold,silver,bronze,total}, awards_json, bf_tank_name, leaderboard_rank_overall`
`leaderboard_snapshots` table for historical rank tracking.

## Known Issues / Next Steps
1. Player card cache stale — key on stats hash, not just `tank_id`
2. Wire `leaderboard_history` into `/ask` SQL layer
3. SQL color/rank filters for cups/kills ("most gold cups among blue")
4. Split bot.py → `banner.py`, `tankpit_api.py`, `ask.py`
5. Bible refresh cron (no schedule yet)
6. Prune unused deps: `beautifulsoup4`, `lxml`
7. Delete legacy files: `tankpit.db`, `tank_cache.pkl`, `seen_posts.json` in bot dir

## Env Vars
```
DISCORD_TOKEN=...
GUILD_ID=615551999701811221       # test
GUILD_ID_2=311890399767822359     # production
```

## Rebuild Bible
```bash
cd ~/tankpit-ai && source venv/bin/activate
python rebuild_bible.py --scraped-dir scraped/profiles --output bible_chunks.json
# ~20-30 min; requires nomic-embed on 8081
```
