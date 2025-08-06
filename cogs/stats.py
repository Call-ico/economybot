
import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, timedelta
import pytz

STATS_FILE = "stats.json"

def load_stats():
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

class Stats(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.reset_stats_daily.start()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        stats = load_stats()
        uid = str(member.id)
        now = int(datetime.now(pytz.timezone("Europe/Moscow")).timestamp())

        if uid not in stats:
            stats[uid] = {
                "voice_minutes": 0,
                "voice_gold": 0,
                "messages": 0,
                "message_gold": 0,
                "voice_enter": None
            }

        # Вход в голосовой канал
        if before.channel is None and after.channel is not None:
            stats[uid]["voice_enter"] = now

        # Выход из голосового канала
        if before.channel is not None and after.channel is None and stats[uid]["voice_enter"]:
            minutes = (now - stats[uid]["voice_enter"]) // 60
            stats[uid]["voice_minutes"] += minutes
            stats[uid]["voice_gold"] += minutes  # если голда = минуты
            stats[uid]["voice_enter"] = None

        save_stats(stats)

    @tasks.loop(minutes=1)
    async def reset_stats_daily(self):
        now = datetime.now(pytz.timezone("Europe/Moscow"))
        if now.hour == 4 and now.minute == 0:
            stats = load_stats()
            for uid in stats:
                stats[uid]["voice_minutes"] = 0
                stats[uid]["voice_gold"] = 0
                stats[uid]["voice_enter"] = None
            save_stats(stats)

async def setup(client):
    await client.add_cog(Stats(client))
