from base import EconomyBot

import discord
from discord import app_commands

from datetime import datetime
from discord.ext import commands

from PIL import Image, ImageDraw, ImageFont
import io
from discord.ui import View, Button
from modules.inventory_funcs import shop_items


class ShopButton(Button):
    def __init__(self):
        # Используем эмодзи первого товара для кнопки
        first_emoji = shop_items[0]["name"].split()[0] if shop_items else "🛒"
        super().__init__(
            label="Открыть магазин",
            style=discord.ButtonStyle.success,
            emoji=first_emoji,
            custom_id="shop_button"
        )

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="МАГАЗИН", color=discord.Color.gold())
        desc = ""
        for item in shop_items:
            # Парсим эмодзи и название
            parts = item["name"].split(" ", 1)
            emoji = parts[0] if len(parts) > 1 else ""
            name = parts[1].upper() if len(parts) > 1 else item["name"].upper()
            desc += f"{emoji} {name} -- {item['cost']} <:gold:1396897616729735299>\n{item['info']}\nID: {item['id']}\n"
        embed.description = desc
        await interaction.response.send_message(embed=embed, ephemeral=True)

class CommandsButton(Button):
    def __init__(self):
        super().__init__(
            label="Команды",
            style=discord.ButtonStyle.primary,
            emoji="📖",
            custom_id="commands_button"
        )

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Справка по командам", color=discord.Color.blue())
        embed.description = (
            "**Экономика и банк**\n"
            "/баланс [@участник] — баланс (кошелёк/банк)\n"
            "/снять <сумма*> — снять с банка\n"
            "/пополнить <сумма*> — положить в банк\n"
            "/перевести <@участник*> <сумма*> — перевод другому\n"
            "/топ — топ богатых\n"
            "\n**Бонусы**\n"
            "/бонус — ежедневный бонус (раз в 24ч)\n"
            "\n**Магазин и инвентарь**\n"
            "/магазин — магазин предметов\n"
            "/магазин инфо <название предмета*> — инфо о предмете\n"
            "/инвентарь [@участник] — ваш инвентарь\n"
            "/купить <название или id предмета*> — купить предмет\n"
            "/продать <название предмета*> — продать предмет\n"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class FunButton(Button):
    def __init__(self):
        super().__init__(
            label="Развлечения",
            style=discord.ButtonStyle.secondary,
            emoji="🎲",
            custom_id="fun_button"
        )

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Развлечения", color=discord.Color.purple())
        embed.description = (
            "\n**Развлечения**\n"
            "/монетка <орел/решка> <сумма> — подбросить монетку\n"
            "/слоты <сумма> — игровые слоты\n"
            "/кости <сумма> [ставка_на] — кости (1-6, по умолчанию 6)"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ShopView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ShopButton())
        self.add_item(CommandsButton())
        self.add_item(FunButton())


class MainBank(commands.Cog):
    def __init__(self, client: EconomyBot):
        self.client = client
        self.bank = self.client.db.bank
        self.tree = client.tree

    def create_balance_image(self, title, wallet_amt, bank_amt, net_amt, username):
        img = Image.new('RGBA', (400, 180), (30, 30, 30, 255))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype('arial.ttf', 24)
        small_font = ImageFont.truetype('arial.ttf', 18)
        # Title
        draw.text((20, 10), title, font=font, fill=(255, 215, 0))
        # Wallet
        draw.text((20, 60), f"Кошелёк: {wallet_amt}", font=small_font, fill=(255, 255, 255))
        # Bank
        draw.text((20, 90), f"Банк: {bank_amt}", font=small_font, fill=(255, 255, 255))
        # Total
        draw.text((20, 120), f"Всего: {net_amt}", font=small_font, fill=(255, 255, 255))
        # Username
        draw.text((20, 150), f"{username}", font=small_font, fill=(180, 180, 180))
        # Gold icon (optional)
        try:
            gold = Image.open('assets/gold.png').resize((32, 32))
            img.paste(gold, (340, 60), gold)
            img.paste(gold, (340, 90), gold)
            img.paste(gold, (340, 120), gold)
        except Exception:
            pass
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def create_transfer_receipt(self, sender, recipient, amount, balance, banker_name=None):
        from datetime import datetime, timedelta
        img = Image.new('RGBA', (400, 210), (30, 30, 30, 255))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype('arial.ttf', 22)
            small_font = ImageFont.truetype('arial.ttf', 16)
        except Exception:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        draw.rectangle([0, 0, 399, 209], outline=(80, 80, 80), width=2)
        draw.text((20, 10), "ЧЕК ПЕРЕВОДА", font=font, fill=(255, 215, 0))
        draw.text((20, 40), f"Отправитель: {sender}", font=small_font, fill=(200, 200, 200))
        draw.text((20, 65), f"Получатель: {recipient}", font=small_font, fill=(200, 200, 200))
        draw.text((20, 90), f"Сумма: {amount}", font=small_font, fill=(255, 255, 255))
        draw.text((20, 115), f"Остаток: {balance}", font=small_font, fill=(255, 255, 255))
        # Время
        try:
            import pytz
            tz = pytz.timezone('Europe/Moscow')
            now = datetime.now(tz)
        except Exception:
            now = datetime.utcnow() + timedelta(hours=3)
        time_str = now.strftime('%d.%m.%Y %H:%M:%S')
        draw.text((20, 140), f"Время (МСК): {time_str}", font=small_font, fill=(180, 180, 180))
        if banker_name:
            draw.text((20, 165), f"Банкир: {banker_name}", font=small_font, fill=(120, 180, 255))
        try:
            gold = Image.open('assets/gold.png').resize((20, 20))
            img.paste(gold, (120, 88), gold)
        except Exception:
            pass
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    @app_commands.command(name="баланс", description="Показать баланс пользователя")
    @app_commands.describe(member="Участник (опционально)")
    async def balance_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        user = member or interaction.user
        user_av = user.display_avatar or user.default_avatar
        if user.bot:
            await interaction.response.send_message("У ботов нет аккаунта", ephemeral=True)
            return
        await self.bank.open_acc(user)
        users = await self.bank.get_acc(user)
        wallet_amt = users[1]
        bank_amt = users[2]
        net_amt = int(wallet_amt + bank_amt)
        buf = self.create_balance_image(f"Баланс {user.name}", wallet_amt, bank_amt, net_amt, user.name)
        file = discord.File(buf, filename="balance.png")
        await interaction.response.send_message(file=file)

    @app_commands.command(name="снять", description="Снять деньги с банка")
    @app_commands.describe(amount="Сумма для снятия (число или 'все')")
    async def withdraw_slash(self, interaction: discord.Interaction, amount: str):
        print(f"[LOG] withdraw_slash called by user={interaction.user} id={interaction.user.id} amount={amount}")
        user = interaction.user
        await self.bank.open_acc(user)
        print(f"[LOG] open_acc completed in withdraw_slash for user={user} id={user.id}")
        users = await self.bank.get_acc(user)
        print(f"[LOG] get_acc result in withdraw_slash: {users}")
        bank_amt = users[2]
        if amount.lower() in ["все", "макс", "all", "max"]:
            print(f"[LOG] withdraw_slash: withdrawing all {bank_amt}")
            await self.bank.update_acc(user, +1 * bank_amt)
            await self.bank.update_acc(user, -1 * bank_amt, "bank")
            await interaction.response.send_message(f"Вы сняли {bank_amt} <:gold:1396897616729735299> из банка.")
            return
        try:
            amount_int = int(amount)
        except ValueError:
            await interaction.response.send_message("Введите корректную сумму!", ephemeral=True)
            return
        if amount_int > bank_amt:
            await interaction.response.send_message(f"У вас нет такой суммы в банке!", ephemeral=True)
            return
        if amount_int < 0:
            await interaction.response.send_message(f"Введите корректную сумму!", ephemeral=True)
            return
        print(f"[LOG] withdraw_slash: withdrawing {amount_int}")
        await self.bank.update_acc(user, +amount_int)
        await self.bank.update_acc(user, -amount_int, "bank")
        await interaction.response.send_message(f"Вы сняли {amount_int} <:gold:1396897616729735299> из банка.")

    @app_commands.command(name="пополнить", description="Положить деньги в банк")
    @app_commands.describe(amount="Сумма для пополнения (число или 'все')")
    async def deposit_slash(self, interaction: discord.Interaction, amount: str):
        print(f"[LOG] deposit_slash called by user={interaction.user} id={interaction.user.id} amount={amount}")
        user = interaction.user
        await self.bank.open_acc(user)
        print(f"[LOG] open_acc completed in deposit_slash for user={user} id={user.id}")
        users = await self.bank.get_acc(user)
        print(f"[LOG] get_acc result in deposit_slash: {users}")
        wallet_amt = users[1]
        if amount.lower() in ["все", "макс", "all", "max"]:
            print(f"[LOG] deposit_slash: depositing all {wallet_amt}")
            await self.bank.update_acc(user, -wallet_amt)
            await self.bank.update_acc(user, +wallet_amt, "bank")
            await interaction.response.send_message(f"Вы пополнили банк на {wallet_amt} <:gold:1396897616729735299>.")
            return
        try:
            amount_int = int(amount)
        except ValueError:
            await interaction.response.send_message("Введите корректную сумму!", ephemeral=True)
            return
        if amount_int > wallet_amt:
            await interaction.response.send_message(f"У вас нет такой суммы в кошельке!", ephemeral=True)
            return
        if amount_int < 0:
            await interaction.response.send_message(f"Введите корректную сумму!", ephemeral=True)
            return
        print(f"[LOG] deposit_slash: depositing {amount_int}")
        await self.bank.update_acc(user, -amount_int)
        await self.bank.update_acc(user, +amount_int, "bank")
        await interaction.response.send_message(f"Вы пополнили банк на {amount_int} <:gold:1396897616729735299>.")

    @app_commands.command(name="перевести", description="Перевести деньги другому участнику")
    @app_commands.describe(member="Кому перевести", amount="Сумма для перевода")
    async def transfer_slash(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        print(f"[LOG] transfer_slash called by user={interaction.user} id={interaction.user.id} to member={member} id={member.id} amount={amount}")
        user = interaction.user
        if member.bot:
            await interaction.response.send_message("У ботов нет аккаунта", ephemeral=True)
            return
        await self.bank.open_acc(user)
        print(f"[LOG] open_acc completed in transfer_slash for user={user} id={user.id}")
        await self.bank.open_acc(member)
        print(f"[LOG] open_acc completed in transfer_slash for member={member} id={member.id}")
        users = await self.bank.get_acc(user)
        print(f"[LOG] get_acc result in transfer_slash: {users}")
        wallet_amt = users[1]
        if amount <= 0:
            await interaction.response.send_message("Введите корректную сумму!", ephemeral=True)
            return
        if amount > wallet_amt:
            await interaction.response.send_message("У вас недостаточно <:gold:1396897616729735299>", ephemeral=True)
            return
        print(f"[LOG] transfer_slash: transferring {amount} from user={user.id} to member={member.id}")
        await self.bank.update_acc(user, -amount)
        await self.bank.update_acc(member, +amount)
        users = await self.bank.get_acc(user)
        buf = self.create_transfer_receipt(user.display_name, member.display_name, amount, users[1], banker_name=user.display_name)
        file = discord.File(buf, filename="transfer.png")
        await interaction.response.send_message(file=file)

    @app_commands.command(name="топ", description="Топ богатых пользователей")
    async def top_slash(self, interaction: discord.Interaction):
        users = await self.bank.get_networth_lb()
        total_money = await self.client.db.execute("SELECT SUM(wallet + bank) FROM bank", fetch="one")
        total_money = total_money[0] if total_money and total_money[0] is not None else 0
        data = []
        index = 1
        for member in users:
            if index > 10:
                break
            user_obj = self.client.get_user(member[0])
            member_amt = member[1]
            mention = user_obj.mention if user_obj else f"<@{member[0]}>"
            if index == 1:
                msg1 = f"**🥇 {mention} -- {member_amt} <:gold:1396897616729735299>**"
                data.append(msg1)
            elif index == 2:
                msg2 = f"**🥈 {mention} -- {member_amt} <:gold:1396897616729735299>**"
                data.append(msg2)
            elif index == 3:
                msg3 = f"**🥉 {mention} -- {member_amt} <:gold:1396897616729735299>**\n"
                data.append(msg3)
            else:
                members = f"**{index} {mention} -- {member_amt} <:gold:1396897616729735299>**"
                data.append(members)
            index += 1
        msg = "\n".join(data)
        em = discord.Embed(
            title=f"Топ {index - 1} самых богатых пользователей (в <:gold:1396897616729735299>)",
            description=f"**Всего денег на сервере:** {total_money:,} <:gold:1396897616729735299>\n\nРейтинг по общей сумме (кошелёк + банк) в <:gold:1396897616729735299> всех пользователей\n\n{msg}",
            color=discord.Color(0x00ff00),
            timestamp=datetime.utcnow()
        )
        em.set_footer(text=f"ГЛОБАЛЬНО - {interaction.guild.name}")
        view = ShopView()
        await interaction.response.send_message(embed=em, view=view)

    @app_commands.command(name="помощь", description="Справка по командам")
    async def help_slash(self, interaction: discord.Interaction):
        em = discord.Embed(title="Справка по командам", color=discord.Color.gold())
        em.description = "**Экономика, банк, магазин, инвентарь, развлечения, админ**\n\nАргументы с * обязательны."
        em.add_field(
            name="Экономика и банк",
            value=(
                "`/баланс [@участник]` — баланс (кошелёк/банк)\n"
                "`/снять <сумма*>` — снять с банка\n"
                "`/пополнить <сумма*>` — положить в банк\n"
                "`/перевести <@участник*> <сумма*>` — перевод другому\n"
                "`/топ` — топ богатых\n"
            ),
            inline=False
        )
        em.add_field(
            name="Бонусы",
            value=(
                "`/бонус` — ежедневный бонус (раз в 24ч)\n"
            ),
            inline=False
        )
        em.add_field(
            name="Магазин и инвентарь",
            value=(
                "`/магазин` — магазин предметов\n"
                "`/магазин инфо <название_предмета*>` — инфо о предмете\n"
                "`/инвентарь [@участник]` — ваш инвентарь\n"
                "`/купить <название_или_id_предмета*>` — купить предмет\n"
                "`/продать <название_предмета*>` — продать предмет\n"
            ),
            inline=False
        )
        em.add_field(
            name="Развлечения",
            value=(
                "`/монетка <орел/решка*> <сумма*>` — подбросить монетку\n"
                "`/слоты <сумма*>` — игровые слоты\n"
                "`/кости <сумма*> [ставка_на]` — кости (1-6, по умолчанию 6)\n"
            ),
            inline=False
        )
        em.add_field(
            name="Админ-команды",
            value=(
                "`/добавить <@участник*> <сумма*> <куда*>` — выдать деньги (кошелёк/банк)\n"
                "`/убрать <@участник*> <сумма*> <откуда*>` — забрать деньги (кошелёк/банк)\n"
                "`/сбросить <@участник*>` — сбросить аккаунт\n"
                "`/бан <@участник*> <время*> [причина]` — бан\n"
                "`/банлист` — список банов\n"
                "`/анбан <@участник*>` — снять бан\n"
            ),
            inline=False
        )
        em.set_footer(text="Алиасы и подробности: используйте /<команда> для справки по аргументам.")
        await interaction.response.send_message(embed=em)


# if you are using 'discord.py >=v2.0' comment(remove) below code
# def setup(client):
#     client.add_cog(MainBank(client))

# if you are using 'discord.py >=v2.0' uncomment(add) below code
async def setup(client):
    await client.add_cog(MainBank(client))
