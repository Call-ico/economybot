
from base import EconomyBot

import discord

from discord.ext import commands
from discord.utils import get

import json
import os
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import io

BAN_FILE = 'bans.json'

def load_bans():
    if not os.path.exists(BAN_FILE):
        return {}
    with open(BAN_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_bans(bans):
    with open(BAN_FILE, 'w', encoding='utf-8') as f:
        json.dump(bans, f, ensure_ascii=False, indent=2)


def is_banker_or_owner():
    async def predicate(ctx):
        if await ctx.bot.is_owner(ctx.author):
            return True
        role = get(ctx.author.roles, name="General Manager") or get(ctx.author.roles, name="Operations Manager") or get(ctx.author.roles, name="Media Head Admin") or get(ctx.author.roles, name="Discord Manager")
        return role is not None
    return commands.check(predicate)

class Admin(commands.Cog):
    def __init__(self, client: EconomyBot):
        self.client = client
        self.bank = self.client.db.bank

    def create_admin_receipt(self, action, member, amount, banker, balance=None):
        img = Image.new('RGBA', (400, 190), (30, 30, 30, 255))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype('arial.ttf', 24)
            small_font = ImageFont.truetype('arial.ttf', 16)
        except Exception:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        draw.rectangle([0, 0, 399, 189], outline=(80, 80, 80), width=2)
        draw.text((20, 10), "ЧЕК", font=font, fill=(255, 215, 0))
        draw.text((20, 45), f"Пользователь: {member.display_name}", font=small_font, fill=(200, 200, 200))
        draw.text((20, 70), f"{action}: {amount:,}", font=small_font, fill=(255, 255, 255))
        if balance is not None:
            draw.text((20, 90), f"Остаток: {balance}", font=small_font, fill=(255, 255, 255))
        # Московское время
        try:
            import pytz
            tz = pytz.timezone('Europe/Moscow')
            now = datetime.now(tz)
        except Exception:
            now = datetime.utcnow() + timedelta(hours=3)
        time_str = now.strftime('%d.%m.%Y %H:%M:%S')
        draw.text((20, 150), f"Время (МСК): {time_str}", font=small_font, fill=(180, 180, 180))
        draw.text((20, 170), f"Банкир: {banker.display_name}", font=small_font, fill=(120, 180, 255))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    @commands.command(aliases=["addmoney"], usage="<участник*: @участник> <сумма*: число> <куда: кошелёк или банк>")
    @is_banker_or_owner()
    @commands.cooldown(3, 2 * 60, commands.BucketType.user)
    async def добавить(self, ctx, member: discord.Member, amount: str, mode: str = "кошелёк"):
        mode = mode.lower()
        if member.bot:
            return await ctx.reply("Нельзя добавить деньги боту", mention_author=False)
        if not amount.isdigit() or int(amount) <= 0:
            return await ctx.reply("Пожалуйста, введите корректную сумму")
        if mode not in ["кошелёк", "банк"]:
            return await ctx.reply("Пожалуйста, укажите либо кошелёк, либо банк")

        limit = 1_000_000_000
        amount = int(amount)
        if amount > limit:
            return await ctx.reply(f"Нельзя добавить больше {limit:,}")

        await self.bank.open_acc(member)
        await self.bank.update_acc(member, +amount, "wallet" if mode == "кошелёк" else "bank")
        users = await self.bank.get_acc(member)
        balance = users[1] if mode == "кошелёк" else users[2]
        buf = self.create_admin_receipt("Добавлено", member, amount, ctx.author, balance=balance)
        file = discord.File(buf, filename="admin_receipt.png")
        await ctx.reply(f"Вы добавили {amount:,} <:gold:1396897616729735299> в {mode} пользователя {member.mention}", file=file, mention_author=False)
        
        # Лог админской операции в форум-канал
        forum_channel_id = 1396619305763733686
        forum_channel = ctx.guild.get_channel(forum_channel_id)
        if forum_channel and hasattr(forum_channel, 'create_thread'):
            thread_title = f"Админ: Добавление денег ({member.name})"
            log_content = f"""
**АДМИНСКАЯ ОПЕРАЦИЯ: ДОБАВЛЕНИЕ ДЕНЕГ**
👤 Администратор: {ctx.author.mention}
👤 Получатель: {member.mention}
💰 Сумма: {amount:,} <:gold:1396897616729735299>
🏦 Куда: {mode}
💳 Баланс после операции: {balance:,} <:gold:1396897616729735299>
⏰ Время: <t:{int(datetime.utcnow().timestamp())}:f>
            """
            try:
                thread = await forum_channel.create_thread(name=thread_title, content=log_content)
            except Exception as e:
                print(f"Ошибка создания лога админской операции: {e}")

    @commands.command(aliases=["remoney"], usage="<участник*: @участник> <сумма*: число> <откуда: кошелёк или банк>")
    @is_banker_or_owner()
    @commands.cooldown(3, 2 * 60, commands.BucketType.user)
    async def убрать(self, ctx, member: discord.Member, amount: str, mode: str = "кошелёк"):
        mode = mode.lower()
        if member.bot:
            return await ctx.reply("Нельзя убрать деньги у бота", mention_author=False)
        if not amount.isdigit() or int(amount) <= 0:
            return await ctx.reply("Пожалуйста, введите корректную сумму")
        if mode not in ["кошелёк", "банк"]:
            return await ctx.reply("Пожалуйста, укажите либо кошелёк, либо банк")

        amount = int(amount)
        await self.bank.open_acc(member)

        users = await self.bank.get_acc(member)
        user_amt = users[2 if mode == "банк" else 1]
        if user_amt < amount:
            return await ctx.reply(
                f"Можно убрать только {user_amt:,} <:gold:1396897616729735299> из {mode} пользователя {member.mention}"
            )

        await self.bank.update_acc(member, -amount, "wallet" if mode == "кошелёк" else "bank")
        users = await self.bank.get_acc(member)
        balance = users[1] if mode == "кошелёк" else users[2]
        buf = self.create_admin_receipt("Снято", member, amount, ctx.author, balance=balance)
        file = discord.File(buf, filename="admin_receipt.png")
        await ctx.reply(f"Вы убрали {amount:,} <:gold:1396897616729735299> из {mode} пользователя {member.mention}", file=file, mention_author=False)
        
        # Лог админской операции в форум-канал
        forum_channel_id = 1396619305763733686
        forum_channel = ctx.guild.get_channel(forum_channel_id)
        if forum_channel and hasattr(forum_channel, 'create_thread'):
            thread_title = f"Админ: Снятие денег ({member.name})"
            log_content = f"""
**АДМИНСКАЯ ОПЕРАЦИЯ: СНЯТИЕ ДЕНЕГ**
👤 Администратор: {ctx.author.mention}
👤 Пользователь: {member.mention}
💰 Сумма: {amount:,} <:gold:1396897616729735299>
🏦 Откуда: {mode}
💳 Баланс после операции: {balance:,} <:gold:1396897616729735299>
⏰ Время: <t:{int(datetime.utcnow().timestamp())}:f>
            """
            try:
                thread = await forum_channel.create_thread(name=thread_title, content=log_content)
            except Exception as e:
                print(f"Ошибка создания лога админской операции: {e}")

    @commands.command(aliases=["reset_user"], usage="<участник*: @участник>")
    @is_banker_or_owner()
    @commands.cooldown(2, 3 * 60, commands.BucketType.user)
    async def сбросить(self, ctx, member: discord.Member):
        if member.bot:
            return await ctx.reply("У ботов нет аккаунта", mention_author=False)

        await self.bank.open_acc(member)
        conn = await self.bank._db.connect()
        await self.bank._db.run(
            f"UPDATE bank SET wallet = 0, bank = 0 WHERE userID = ?",
            (member.id,), conn=conn
        )
        await conn.close()
        buf = self.create_admin_receipt("Сброшено", member, 0, ctx.author)
        file = discord.File(buf, filename="admin_receipt.png")
        await ctx.reply(f"Баланс пользователя {member.mention} был обнулён", file=file, mention_author=False)

    @commands.command(aliases=["ban"], usage="<участник: @участник> <время: 1h/30m/2d> <причина: текст>")
    @is_banker_or_owner()
    async def бан(self, ctx, member: discord.Member, duration: str, *, reason: str = "Без причины"):
        if member.bot:
            return await ctx.reply("Нельзя забанить бота", mention_author=False)
        bans = load_bans()
        uid = str(member.id)
        if uid in bans:
            return await ctx.reply("Пользователь уже забанен", mention_author=False)
        # Парсинг времени
        try:
            if duration.endswith('h'):
                delta = timedelta(hours=int(duration[:-1]))
            elif duration.endswith('m'):
                delta = timedelta(minutes=int(duration[:-1]))
            elif duration.endswith('d'):
                delta = timedelta(days=int(duration[:-1]))
            else:
                return await ctx.reply("Формат времени: 1h, 30m, 2d", mention_author=False)
        except Exception:
            return await ctx.reply("Некорректное время. Пример: 1h, 30m, 2d", mention_author=False)
        until = (datetime.utcnow() + delta).timestamp()
        bans[uid] = {"until": until, "reason": reason, "by": ctx.author.id}
        save_bans(bans)
        await ctx.reply(f"Пользователь {member.mention} забанен до <t:{int(until)}:f> по причине: {reason}", mention_author=False)

    @commands.command(aliases=["banlist"], usage="")
    @is_banker_or_owner()
    async def банлист(self, ctx):
        bans = load_bans()
        if not bans:
            return await ctx.reply("Список банов пуст", mention_author=False)
        lines = []
        now = datetime.utcnow().timestamp()
        for uid, info in bans.items():
            left = int(info["until"] - now)
            if left < 0:
                left = 0
            m = ctx.guild.get_member(int(uid))
            name = m.mention if m else uid
            lines.append(f"{name} — ещё {timedelta(seconds=left)} | {info['reason']}")
        await ctx.reply("\n".join(lines), mention_author=False)

    @commands.command(aliases=["unban"], usage="<участник: @участник>")
    @is_banker_or_owner()
    async def анбан(self, ctx, member: discord.Member):
        bans = load_bans()
        uid = str(member.id)
        if uid not in bans:
            return await ctx.reply("Пользователь не в бане", mention_author=False)
        bans.pop(uid)
        save_bans(bans)
        await ctx.reply(f"Пользователь {member.mention} разбанен", mention_author=False)


# if you are using 'discord.py >=v2.0' comment(remove) below code
# def setup(client):
#     client.add_cog(Admin(client))

# if you are using 'discord.py >=v2.0' uncomment(add) below code
async def setup(client):
    await client.add_cog(Admin(client))
