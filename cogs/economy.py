from base import EconomyBot

from numpy import random

from discord.ext import commands

from PIL import Image, ImageDraw, ImageFont
import io
from datetime import datetime, timedelta
from discord import app_commands
import discord


class Economy(commands.Cog):
    def __init__(self, client: EconomyBot):
        self.client = client
        self.bank = self.client.db.bank

    def create_bonus_image(self, amount, username):
        img = Image.new('RGBA', (400, 100), (30, 30, 30, 255))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype('arial.ttf', 28)
        small_font = ImageFont.truetype('arial.ttf', 18)
        draw.text((20, 20), f"Ваша ежедневная награда:", font=font, fill=(255, 215, 0))
        draw.text((20, 60), f"{amount:,} ", font=font, fill=(255, 255, 255))
        draw.text((200, 60), username, font=small_font, fill=(180, 180, 180))
        try:
            gold = Image.open('assets/gold.png').resize((32, 32))
            img.paste(gold, (150, 55), gold)
        except Exception:
            pass
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    @app_commands.command(name="бонус", description="Получить ежедневный бонус")
    async def bonus_slash(self, interaction: discord.Interaction):
        import json
        import os
        user = interaction.user
        user_id = str(user.id)
        now = datetime.utcnow().timestamp()
        file_path = os.path.join(os.path.dirname(__file__), '..', 'bonus_timestamps.json')
        file_path = os.path.abspath(file_path)
        # Читаем json
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {"bonus_timestamps": {}}
        timestamps = data.get("bonus_timestamps", {})
        last = timestamps.get(user_id, 0)
        cooldown = 60 * 60 * 24
        if now - last < cooldown:
            retry_after = int(cooldown - (now - last))
            hours = retry_after // 3600
            minutes = (retry_after % 3600) // 60
            seconds = retry_after % 60
            await interaction.response.send_message(
                f"Вы уже получили бонус. Попробуйте снова через {hours}ч {minutes}м {seconds}с.",
                ephemeral=True
            )
            return
        # Выдаём бонус
        await self.bank.open_acc(user)
        await self.bank.update_acc(user, 30)
        await interaction.response.send_message(f"Вам начислено 30 <:gold:1396929958965940286>!")
        # Сохраняем время
        timestamps[user_id] = now
        data["bonus_timestamps"] = timestamps
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
    @commands.command(name="топ", aliases=["top", "лидеры"])
    async def leaderboard(self, ctx):
        """Показывает топ 10 богачей сервера"""
        # ID канала для отображения топа (замените на нужный)
        LEADERBOARD_CHANNEL_ID = ctx.channel.id
        
        # Файл для хранения ID сообщения с топом
        LEADERBOARD_MESSAGE_ID_FILE = "balance_leaderboard_message_id.txt"
        
        try:
            # Пытаемся прочитать ID последнего сообщения с топом
            message_id = None
            try:
                with open(LEADERBOARD_MESSAGE_ID_FILE, "r") as f:
                    message_id = f.read().strip()
            except FileNotFoundError:
                pass
            
            # Обновляем или создаем сообщение с топом
            new_message_id = await self.bank.update_leaderboard_message(
                self.client,
                LEADERBOARD_CHANNEL_ID,
                message_id
            )
            
            if new_message_id:
                # Сохраняем новый ID сообщения
                with open(LEADERBOARD_MESSAGE_ID_FILE, "w") as f:
                    f.write(str(new_message_id))
                    
                if message_id != str(new_message_id):
                    await ctx.message.delete()  # Удаляем команду пользователя
                    
        except Exception as e:
            print(f"Ошибка при обновлении топа: {e}")
            await ctx.send("Произошла ошибка при обновлении топа", delete_after=5)


# if you are using 'discord.py >=v2.0' comment(remove) below code
# def setup(client):
#     client.add_cog(Economy(client))

# if you are using 'discord.py >=v2.0' uncomment(add) below code
async def setup(client):
    await client.add_cog(Economy(client))
