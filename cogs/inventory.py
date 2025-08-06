
from base import EconomyBot
import discord
import discord.ui

from discord.ext import commands
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
from discord import app_commands

# --- View для управления покупками ---
class PurchaseActionView(discord.ui.View):
    def __init__(self, user_id, item_name, item_cost, bot, inv, bank, thread, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = user_id
        self.item_name = item_name
        self.item_cost = item_cost
        self.bot = bot
        self.inv = inv
        self.bank = bank
        self.thread = thread

    @discord.ui.button(label="В разработке", style=discord.ButtonStyle.primary, custom_id="in_dev")
    async def in_dev(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.guild.get_member(self.user_id)
        if not user:
            await interaction.response.send_message("Пользователь не найден.", ephemeral=True)
            return
        await self.inv.update_acc(user, -1, self.item_name)
        await self.thread.send(f"🔧 Предмет **{self.item_name}** у {user.mention} взят в разработку {interaction.user.mention} ({interaction.user})\n⏰ <t:{int(datetime.utcnow().timestamp())}:f>")
        await interaction.response.send_message(f"Предмет удалён из инвентаря пользователя и отмечен как 'В разработке'.", ephemeral=True)

    @discord.ui.button(label="Выдано", style=discord.ButtonStyle.success, custom_id="issued")
    async def issued(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.guild.get_member(self.user_id)
        await self.thread.send(f"✅ Предмет **{self.item_name}** выдан {user.mention} {interaction.user.mention} ({interaction.user})\n⏰ <t:{int(datetime.utcnow().timestamp())}:f>")
        await interaction.response.send_message(f"Отмечено как 'Выдано'.", ephemeral=True)

    @discord.ui.button(label="Отклонено", style=discord.ButtonStyle.danger, custom_id="declined")
    async def declined(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.guild.get_member(self.user_id)
        if not user:
            await interaction.response.send_message("Пользователь не найден.", ephemeral=True)
            return
        await self.inv.update_acc(user, -1, self.item_name)
        await self.bank.update_acc(user, +self.item_cost)
        await self.thread.send(f"❌ Покупка **{self.item_name}** у {user.mention} отклонена {interaction.user.mention} ({interaction.user})\n💸 Возврат: {self.item_cost:,} <:gold:1396929958965940286>\n⏰ <t:{int(datetime.utcnow().timestamp())}:f>")
        await interaction.response.send_message(f"Покупка отклонена, предмет удалён и средства возвращены.", ephemeral=True)


class Inventory(commands.Cog):
    def __init__(self, client: EconomyBot):
        self.client = client
        self.inv = self.client.db.inv
        self.bank = self.client.db.bank

    def create_receipt_image(self, item_name, item_cost, username, balance=None):
        from datetime import datetime, timedelta, timezone
        import pytz
        img = Image.new('RGBA', (400, 190), (30, 30, 30, 255))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype('arial.ttf', 24)
            small_font = ImageFont.truetype('arial.ttf', 16)
        except Exception:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        draw.rectangle([0, 0, 399, 189], outline=(80, 80, 80), width=2)
        draw.text((20, 10), "ЧЕК О ПОКУПКЕ", font=font, fill=(255, 215, 0))
        draw.text((20, 45), f"Пользователь: {username}", font=small_font, fill=(200, 200, 200))
        clean_name = item_name.split(' ', 1)[-1]
        draw.text((20, 70), f"Товар: {clean_name}", font=small_font, fill=(255, 255, 255))
        draw.text((20, 95), f"Сумма: {item_cost} ", font=small_font, fill=(255, 255, 255))
        if balance is not None:
            draw.text((20, 115), f"Остаток: {balance}", font=small_font, fill=(255, 255, 255))
        try:
            gold = Image.open('assets/gold.png').resize((20, 20))
            img.paste(gold, (120, 92), gold)
        except Exception:
            pass
        # Московское время
        try:
            import pytz
            tz = pytz.timezone('Europe/Moscow')
            now = datetime.now(tz)
        except Exception:
            now = datetime.utcnow() + timedelta(hours=3)
        time_str = now.strftime('%d.%m.%Y %H:%M:%S')
        draw.text((20, 150), f"Время (МСК): {time_str}", font=small_font, fill=(180, 180, 180))
        draw.text((20, 170), "Банкир: iCCup Bot", font=small_font, fill=(120, 180, 255))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    async def show_inventory(self, interaction: discord.Interaction, member: discord.Member = None):
        """Основная логика отображения инвентаря"""
        user = member or interaction.user
        user_av = user.display_avatar or user.default_avatar
        if user.bot:
            await interaction.response.send_message("У ботов нет аккаунта", ephemeral=True)
            return
        await self.inv.open_acc(user)
        em = discord.Embed(color=0x00ff00)
        x = 1
        for item in self.inv.shop_items:
            name = item["name"]
            item_id = item["id"]
            data = await self.inv.update_acc(user, 0, name)
            if data[0] >= 1:
                x += 1
                em.add_field(
                    name=f"{name.upper()} - {data[0]}", value=f"ID: {item_id}", inline=False)
        em.set_author(name=f"Инвентарь {user.name}", icon_url=user_av.url)
        if x == 1:
            em.description = "Здесь отображаются купленные вами предметы..."
        await interaction.response.send_message(embed=em)

    @app_commands.command(name="инвентарь", description="Показать инвентарь пользователя")
    @app_commands.describe(member="Участник (опционально)")
    async def inventory_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        """Слеш-команда для отображения инвентаря"""
        await self.show_inventory(interaction, member)

    @app_commands.command(name="купить", description="Купить предмет по названию или ID")
    @app_commands.describe(item_query="Название или ID предмета")
    @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
    async def buy_slash(self, interaction: discord.Interaction, item_query: str):
        user = interaction.user
        # Проверка, что команда вызывается только в гильдии
        if not interaction.guild:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        await self.bank.open_acc(user)
        await self.inv.open_acc(user)
        # Улучшенный поиск предмета (безопасность и удобство)
        item_query_clean = item_query.strip().lower()
        item = None
        if item_query_clean.isdigit():
            item_id = int(item_query_clean)
            for it in self.inv.shop_items:
                if it["id"] == item_id:
                    item = it
                    break
        if not item:
            for it in self.inv.shop_items:
                if item_query_clean == it["name"].strip().lower():
                    item = it
                    break
        if not item:
            await interaction.response.send_message(f"Нет предмета с названием или id `{item_query}`", ephemeral=True)
            return
        # Проверка на отрицательную стоимость
        if item["cost"] < 0:
            await interaction.response.send_message("Ошибка: стоимость предмета некорректна.", ephemeral=True)
            return
        users = await self.bank.get_acc(user)
        if users[1] < item["cost"]:
            await interaction.response.send_message(f"У вас недостаточно <:gold:1396929958965940286> для покупки {item['name']}", ephemeral=True)
            return
        try:
            await self.inv.update_acc(user, +1, item["name"])
            await self.bank.update_acc(user, -item["cost"])
        except Exception as e:
            await interaction.response.send_message(f"Ошибка при обновлении баланса: {e}", ephemeral=True)
            return
        users = await self.bank.get_acc(user)
        buf = self.create_receipt_image(item["name"], item["cost"], user.name, balance=users[1])
        file = discord.File(buf, filename="receipt.png")
        await interaction.response.send_message(file=file)
        # Дублирование чека в форум-канал
        forum_channel_id = 1396619305763733686
        forum_channel = interaction.guild.get_channel(forum_channel_id)
        if forum_channel and hasattr(forum_channel, 'create_thread'):
            thread_title = f"Покупка: {item['name']} ({user.name})"
            log_content = f"""
**ПОКУПКА ПРЕДМЕТА**
👤 Покупатель: {user.mention}
🛒 Предмет: **{item['name']}**
💰 Стоимость: {item['cost']:,} <:gold:1396929958965940286>
💳 Баланс после покупки: {users[1]:,} <:gold:1396929958965940286>
⏰ Время: <t:{int(datetime.utcnow().timestamp())}:f>
            """
            try:
                thread = await forum_channel.create_thread(name=thread_title, content=log_content)
                view = PurchaseActionView(user.id, item["name"], item["cost"], self.client, self.inv, self.bank, thread)
                await thread.send(f"Действия с покупкой:", view=view)
            except Exception as e:
                await interaction.followup.send(f"Ошибка создания лога покупки: {e}", ephemeral=True)
        else:
            try:
                log_content = f"""
**ПОКУПКА ПРЕДМЕТА**
👤 Покупатель: {user.mention}
🛒 Предмет: **{item['name']}**
💰 Стоимость: {item['cost']:,} <:gold:1396929958965940286>
💳 Баланс после покупки: {users[1]:,} <:gold:1396929958965940286>
⏰ Время: <t:{int(datetime.utcnow().timestamp())}:f>
                """
                await forum_channel.send(log_content)
            except Exception as e:
                await interaction.followup.send(f"Не удалось отправить лог в канал: {e}", ephemeral=True)
        # --- Выдача роли ---
        # Для безопасности используем словарь с id ролей (пример)
        role_ids = {
            "Shadow Fiend": 123456789012345678,  # замените на реальные id ролей
            "Necromancer": 123456789012345679,
            "Majority": 123456789012345680,
            "Royal Crown": 123456789012345681,
            "уникальная роль": 123456789012345682,
        }
        role_name = item["name"].split(' ', 1)[-1]
        if role_name in role_ids:
            guild = interaction.guild
            role = guild.get_role(role_ids[role_name])
            if role:
                try:
                    await user.add_roles(role, reason="Покупка предмета через бота")
                    await interaction.followup.send(f"Вам выдана роль {role.name}!", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"Ошибка выдачи роли: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"Роль {role_name} не найдена на сервере. Обратитесь к администратору.", ephemeral=True)

    @app_commands.command(name="продать", description="Продать предмет по названию или ID")
    @app_commands.describe(item_query="Название или ID предмета")
    @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
    async def sell_slash(self, interaction: discord.Interaction, item_query: str):
        user = interaction.user
        if not interaction.guild:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        await self.bank.open_acc(user)
        await self.inv.open_acc(user)
        item_query_clean = item_query.strip().lower()
        item = None
        if item_query_clean.isdigit():
            item_id = int(item_query_clean)
            for it in self.inv.shop_items:
                if it["id"] == item_id:
                    item = it
                    break
        if not item:
            for it in self.inv.shop_items:
                if item_query_clean == it["name"].strip().lower():
                    item = it
                    break
        if not item:
            await interaction.response.send_message(f"Нет предмета с названием или id `{item_query}`", ephemeral=True)
            return
        quantity = await self.inv.update_acc(user, 0, item["name"])
        if quantity[0] < 1:
            await interaction.response.send_message(f"У вас нет {item['name']} в инвентаре", ephemeral=True)
            return
        cost = int(round(item["cost"] / 2, 0))
        if cost < 0:
            await interaction.response.send_message("Ошибка: стоимость предмета некорректна.", ephemeral=True)
            return
        try:
            await self.inv.update_acc(user, -1, item["name"])
            await self.bank.update_acc(user, +cost)
        except Exception as e:
            await interaction.response.send_message(f"Ошибка при обновлении баланса: {e}", ephemeral=True)
            return
        await interaction.response.send_message(f"Вы продали {item['name']} за {cost:,} <:gold:1396929958965940286>")
        # Дублирование лога продажи в форум-канал
        forum_channel_id = 1396619305763733686
        forum_channel = interaction.guild.get_channel(forum_channel_id)
        if forum_channel and hasattr(forum_channel, 'create_thread'):
            thread_title = f"Продажа: {item['name']} ({user.name})"
            log_content = f"""
**ПРОДАЖА ПРЕДМЕТА**
👤 Продавец: {user.mention}
🛒 Предмет: **{item['name']}**
💰 Получено: {cost:,} <:gold:1396929958965940286>
⏰ Время: <t:{int(datetime.utcnow().timestamp())}:f>
            """
            try:
                thread = await forum_channel.create_thread(name=thread_title, content=log_content)
            except Exception as e:
                await interaction.followup.send(f"Ошибка создания лога продажи: {e}", ephemeral=True)

    @commands.command(aliases=["inv"], usage="<участник: @участник>")
    @commands.guild_only()
    async def инвентарь(self, ctx, member: discord.Member = None):
        user = member or ctx.author
        user_av = user.display_avatar or user.default_avatar
        if user.bot:
            return await ctx.reply("У ботов нет аккаунта", mention_author=False)
        await self.inv.open_acc(user)

        em = discord.Embed(color=0x00ff00)
        x = 1
        for item in self.inv.shop_items:
            name = item["name"]
            item_id = item["id"]

            data = await self.inv.update_acc(user, 0, name)
            if data[0] >= 1:
                x += 1
                em.add_field(
                    name=f"{name.upper()} - {data[0]}", value=f"ID: {item_id}", inline=False)

        em.set_author(name=f"Инвентарь {user.name}", icon_url=user_av.url)
        if x == 1:
            em.description = "Здесь отображаются купленные вами предметы..."

        await ctx.reply(embed=em, mention_author=False)

    @commands.command(aliases=["buy"], usage="<название_или_id_предмета*: строка или число>")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def купить(self, ctx, *, item_query: str):
        user = ctx.author
        if not ctx.guild:
            return await ctx.reply("Команда доступна только на сервере", mention_author=False)
        await self.bank.open_acc(user)
        await self.inv.open_acc(user)
        item_query_clean = item_query.strip().lower()
        item = None
        if item_query_clean.isdigit():
            item_id = int(item_query_clean)
            for it in self.inv.shop_items:
                if it["id"] == item_id:
                    item = it
                    break
        if not item:
            for it in self.inv.shop_items:
                if item_query_clean == it["name"].strip().lower():
                    item = it
                    break
        if not item:
            return await ctx.reply(f"Нет предмета с названием или id `{item_query}`", mention_author=False)
        if item["cost"] < 0:
            return await ctx.reply("Ошибка: стоимость предмета некорректна.", mention_author=False)
        users = await self.bank.get_acc(user)
        if users[1] < item["cost"]:
            return await ctx.reply(f"У вас недостаточно <:gold:1396929958965940286> для покупки {item['name']}", mention_author=False)
        try:
            await self.inv.update_acc(user, +1, item["name"])
            await self.bank.update_acc(user, -item["cost"])
        except Exception as e:
            return await ctx.reply(f"Ошибка при обновлении баланса: {e}", mention_author=False)
        users = await self.bank.get_acc(user)
        buf = self.create_receipt_image(item["name"], item["cost"], user.name, balance=users[1])
        file = discord.File(buf, filename="receipt.png")
        await ctx.reply(file=file, mention_author=False)
        # Дублирование чека в форум-канал
        forum_channel_id = 1396619305763733686
        forum_channel = ctx.guild.get_channel(forum_channel_id)
        if forum_channel and hasattr(forum_channel, 'create_thread'):
            thread_title = f"Покупка: {item['name']} ({user.name})"
            log_content = f"""
**ПОКУПКА ПРЕДМЕТА**
👤 Покупатель: {user.mention}
🛒 Предмет: **{item['name']}**
💰 Стоимость: {item['cost']:,} <:gold:1396929958965940286>
💳 Баланс после покупки: {users[1]:,} <:gold:1396929958965940286>
⏰ Время: <t:{int(datetime.utcnow().timestamp())}:f>
            """
            try:
                thread = await forum_channel.create_thread(name=thread_title, content=log_content)
                view = PurchaseActionView(user.id, item["name"], item["cost"], self.client, self.inv, self.bank, thread)
                await thread.send(f"Действия с покупкой:", view=view)
            except Exception as e:
                await ctx.reply(f"Ошибка создания лога покупки: {e}", mention_author=False)
        else:
            try:
                log_content = f"""
**ПОКУПКА ПРЕДМЕТА**
👤 Покупатель: {user.mention}
🛒 Предмет: **{item['name']}**
💰 Стоимость: {item['cost']:,} <:gold:1396929958965940286>
💳 Баланс после покупки: {users[1]:,} <:gold:1396929958965940286>
⏰ Время: <t:{int(datetime.utcnow().timestamp())}:f>
                """
                await forum_channel.send(log_content)
            except Exception as e:
                await ctx.reply(f"Не удалось отправить лог в канал: {e}", mention_author=False)
        # --- Выдача роли ---
        role_ids = {
            "Shadow Fiend": 123456789012345678,
            "Necromancer": 123456789012345679,
            "Majority": 123456789012345680,
            "Royal Crown": 123456789012345681,
            "уникальная роль": 123456789012345682,
        }
        role_name = item["name"].split(' ', 1)[-1]
        if role_name in role_ids:
            guild = ctx.guild
            role = guild.get_role(role_ids[role_name])
            if role:
                try:
                    await user.add_roles(role, reason="Покупка предмета через бота")
                    await ctx.reply(f"Вам выдана роль {role.name}!", mention_author=False)
                except Exception as e:
                    await ctx.reply(f"Ошибка выдачи роли: {e}", mention_author=False)
            else:
                await ctx.reply(f"Роль {role_name} не найдена на сервере. Обратитесь к администратору.", mention_author=False)
        return

    @commands.command(aliases=["sell"], usage="<название_или_id_предмета*: строка или число>")
    async def продать(self, ctx, *, item_query: str):
        user = ctx.author
        await self.bank.open_acc(user)
        await self.inv.open_acc(user)
        # Поиск по id или названию
        item = None
        if item_query.isdigit():
            item_id = int(item_query)
            for it in self.inv.shop_items:
                if it["id"] == item_id:
                    item = it
                    break
        if not item:
            for it in self.inv.shop_items:
                if item_query.lower() == it["name"].lower():
                    item = it
                    break
        if not item:
            return await ctx.reply(f"Нет предмета с названием или id `{item_query}`", mention_author=False)
        quantity = await self.inv.update_acc(user, 0, item["name"])
        if quantity[0] < 1:
            return await ctx.reply(f"У вас нет {item['name']} в инвентаре", mention_author=False)
        cost = int(round(item["cost"] / 2, 0))
        await self.inv.update_acc(user, -1, item["name"])
        await self.bank.update_acc(user, +cost)
        
        # Дублирование лога продажи в форум-канал
        forum_channel_id = 1396619305763733686
        forum_channel = ctx.guild.get_channel(forum_channel_id)
        if forum_channel and hasattr(forum_channel, 'create_thread'):
            thread_title = f"Продажа: {item['name']} ({user.name})"
            log_content = f"""
**ПРОДАЖА ПРЕДМЕТА**
👤 Продавец: {user.mention}
🛒 Предмет: **{item['name']}**
💰 Получено: {cost:,} <:gold:1396929958965940286>
⏰ Время: <t:{int(datetime.utcnow().timestamp())}:f>
            """
            try:
                thread = await forum_channel.create_thread(name=thread_title, content=log_content)
            except Exception as e:
                print(f"Ошибка создания лога продажи: {e}")
        
        return await ctx.reply(f"Вы продали {item['name']} за {cost:,} <:gold:1396929958965940286>", mention_author=False)

    @commands.command(usage="<@пользователь> <id_предмета>")
    @commands.has_permissions(administrator=True)
    async def удалить(self, ctx, member: discord.Member, item_id: int):
        await self.inv.open_acc(member)
        # Найти предмет по id
        item = None
        for it in self.inv.shop_items:
            if it["id"] == item_id:
                item = it
                break
        if not item:
            return await ctx.reply(f"Нет предмета с id `{item_id}`", mention_author=False)
        quantity = await self.inv.update_acc(member, 0, item["name"])
        if quantity[0] < 1:
            return await ctx.reply(f"У пользователя нет {item['name']} в инвентаре", mention_author=False)
        await self.inv.update_acc(member, -1, item["name"])
        await ctx.reply(f"У пользователя {member.mention} удалён 1 предмет: {item['name']}", mention_author=False)


# if you are using 'discord.py >=v2.0' comment(remove) below code
# def setup(client):
#     client.add_cog(Inventory(client))

# if you are using 'discord.py >=v2.0' uncomment(add) below code
async def setup(client):
    await client.add_cog(Inventory(client))
