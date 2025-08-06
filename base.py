
from modules import Database
import discord
import os
from discord.ext import commands
from dotenv import load_dotenv, find_dotenv
from modules.config import TOKEN, COMMAND_PREFIX, FILENAME

load_dotenv(find_dotenv(raise_error_if_not_found=True))

class Auth:
    TOKEN = TOKEN
    COMMAND_PREFIX = COMMAND_PREFIX
    FILENAME = FILENAME

class EconomyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = Database(Auth.FILENAME)

    async def on_message(self, message):
        if message.guild is None or message.guild.id != 614513381600264202:
            return
        await super().on_message(message)

    async def on_command(self, ctx):
        if ctx.guild is None or ctx.guild.id != 614513381600264202:
            return

    async def setup_hook(self):
        await self.db.bank.setup_log_cleaning()
        await self.db.bank.create_table()
        await self.db.inv.create_table()
        print("Таблицы успешно созданы/изменены")
        for file in os.listdir("./cogs"):
            if file.endswith(".py"):
                filename = file[:-3]
                try:
                    await self.load_extension(f"cogs.{filename}")
                    print(f"Загружено расширение: {filename}")
                except Exception as e:
                    print(f"Ошибка при загрузке {filename}: {e}")
                    import traceback
                    traceback.print_exc()
        print("Синхронизация команд...")
        try:
            synced = await self.tree.sync()
            print(f"Синхронизировано {len(synced)} команд")
        except Exception as e:
            print(f"Ошибка синхронизации: {e}")

    async def on_ready(self):
        print(f"Бот {self.user} готов к работе!")
        print(f"ID бота: {self.user.id}")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="/помощь"
            ),
            status=discord.Status.online
        )
        print(f"{self.user.name} теперь онлайн!")
