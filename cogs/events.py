from base import Auth

import discord

from datetime import timedelta
from discord.ext import commands

import json
import os
from datetime import datetime
BAN_FILE = 'bans.json'

def load_bans():
    if not os.path.exists(BAN_FILE):
        return {}
    with open(BAN_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

class Events(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @commands.Cog.listener()
    async def on_command(self, ctx):
        # Глобальная проверка: только нужный сервер
        if ctx.guild is None or ctx.guild.id != 614513381600264202:
            return
        if ctx.command.name in ["банлист", "анбан"]:
            return
        bans = load_bans()
        uid = str(ctx.author.id)
        if uid in bans:
            until = bans[uid]["until"]
            now = datetime.utcnow().timestamp()
            if now < until:
                return await ctx.reply(f"Вы забанены до <t:{int(until)}:f> и не можете использовать команды.", mention_author=False)
            else:
                # Автоматический разбан по истечении срока
                bans.pop(uid)
                with open(BAN_FILE, 'w', encoding='utf-8') as f:
                    json.dump(bans, f, ensure_ascii=False, indent=2)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        user = ctx.author
        if isinstance(error, commands.errors.CommandNotFound):
            return

        if isinstance(error, commands.errors.MissingPermissions) or isinstance(error, commands.errors.NotOwner):
            return await ctx.reply("Вы не можете использовать эту команду")

        if isinstance(error, commands.errors.MemberNotFound):
            return await ctx.reply("Указанный участник не найден или некорректен")

        if isinstance(error, commands.errors.MissingRequiredArgument):
            cmd_parent = ctx.command.parent
            if cmd_parent is not None:
                cmd_name = f"{cmd_parent} {ctx.command.name}"
            else:
                cmd_name = ctx.command.name

            cmd_usage = ctx.command.usage
            aliases = ctx.command.aliases
            cmd_params = list(ctx.command.params.values())

            usage = f"{Auth.COMMAND_PREFIX}{cmd_name} "
            if cmd_usage is None:
                cmd_params = cmd_params[2:] if cmd_params[0].name == "self" else cmd_params[1:]
                params = []
                for param in cmd_params:
                    if param.empty:
                        log = f"<{param.name}*>"
                    else:
                        log = f"<{param.name}>"
                    params.append(log)

                usage += ' '.join(params)
            else:
                usage += cmd_usage

            em = discord.Embed(
                description=f"**Правильное использование**\n`{usage}`"
            )
            if len(aliases) >= 1:
                em.add_field(name="Алиасы", value=', '.join(aliases))
            em.set_footer(text="'*' означает, что аргумент обязателен")
            return await ctx.reply(embed=em, mention_author=False)

        if isinstance(error, commands.errors.CommandOnCooldown):
            time_left = timedelta(seconds=error.retry_after)
            return await ctx.reply(f"Команда на перезарядке. Попробуйте через `{time_left.__str__()}`", mention_author=False)

        raise error


# if you are using 'discord.py >=v2.0' comment(remove) below code
# def setup(client):
#     client.add_cog(Events(client))

# if you are using 'discord.py >=v2.0' uncomment(add) below code
async def setup(client):
    await client.add_cog(Events(client))
