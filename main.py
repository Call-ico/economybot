import discord
import logging
import sys
from base import Auth, EconomyBot
intents = discord.Intents.all()
client = EconomyBot(command_prefix=Auth.COMMAND_PREFIX, intents=intents)

# Настройка логгирования в debug.txt
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler("debug.txt", encoding="utf-8"),
    ]
)

# Перенаправление print в logging
class PrintLogger:
    def write(self, msg):
        if msg.strip():
            logging.debug(msg.strip())
    def flush(self):
        pass

sys.stdout = PrintLogger()
sys.stderr = PrintLogger()

# Импортируем функцию регистрации команды /stats
from bot import setup_stats_command
setup_stats_command(client)

@client.event
async def on_ready():
    # Однократное сообщение в консоль
    sys.__stdout__.write(f"\n✅ Бот успешно запущен как {client.user}\n")
    sys.__stdout__.flush()
    print(f"✅ Бот успешно запущен как {client.user}")
    try:
        synced = await client.tree.sync()
        print(f"✅ Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")

# Ограничение работы только на сервере 614513381600264202
ALLOWED_GUILD_ID = 614513381600264202

@client.check
async def global_guild_check(ctx):
    return ctx.guild and ctx.guild.id == ALLOWED_GUILD_ID

@client.event
async def on_message(message):
    if message.guild is None or message.guild.id != ALLOWED_GUILD_ID:
        return  # Игнорируем сообщения вне нужного сервера и в ЛС
    await client.process_commands(message)

@client.event
async def on_interaction(interaction):
    if not interaction.guild or interaction.guild.id != ALLOWED_GUILD_ID:
        return  # Игнорируем взаимодействия вне нужного сервера и в ЛС
    await client.process_application_commands(interaction)

@client.event
async def on_command_error(ctx, error):
    if not ctx.guild or ctx.guild.id != ALLOWED_GUILD_ID:
        return  # Не отправляем ошибки вне нужного сервера и в ЛС
    await ctx.send(f"Ошибка: {error}")

if __name__ == "__main__":
    client.run(Auth.TOKEN)
