import discord
from discord.ext import commands, tasks
from datetime import datetime

BONUS_ROLE_NAMES = [
    "Shadow Fiend",
    "Necromancer",
    "Majority",
    "Royal Crown",
    # Добавьте другие роли, если нужно
]
BONUS_AMOUNT = 30

class DailyBonus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.give_daily_bonus.start()

    @tasks.loop(hours=24)
    async def give_daily_bonus(self):
        for guild in self.bot.guilds:
            # Работать только на нужном сервере
            if guild.id != 614513381600264202:
                continue
            for member in guild.members:
                if member.bot:
                    continue
                if any(role.name in BONUS_ROLE_NAMES for role in member.roles):
                    await self.bot.db.bank.open_acc(member)
                    await self.bot.db.bank.update_acc(member, BONUS_AMOUNT)
                    # Не отправлять личные сообщения
                    # try:
                    #     await member.send(f"Вам начислено {BONUS_AMOUNT} <:gold:1396929958965940286> за уникальную роль!")
                    # except Exception:
                    #     pass  # Не удалось отправить ЛС

    @give_daily_bonus.before_loop
    async def before_give_daily_bonus(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(DailyBonus(bot)) 
