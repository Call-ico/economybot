from base import EconomyBot

import discord
import asyncio
import json
import time

from typing import List
from numpy import random
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import random as pyrand

COOLDOWN_SECONDS = 3 * 60 * 60  # 3 часа
COOLDOWN_FILE = 'bonus_timestamps.json'

def get_cooldown_key(user_id, game):
    return f"{user_id}_{game}"

def load_timestamps():
    try:
        with open(COOLDOWN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('game_timestamps', {})
    except Exception:
        return {}

def save_timestamps(timestamps):
    try:
        try:
            with open(COOLDOWN_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
        data['game_timestamps'] = timestamps
        with open(COOLDOWN_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения кулдаунов: {e}")

async def check_and_update_cooldown(interaction, game_name):
    user_id = str(interaction.user.id)
    timestamps = load_timestamps()
    key = get_cooldown_key(user_id, game_name)
    now = time.time()
    last = timestamps.get(key, 0)
    if now - last < COOLDOWN_SECONDS:
        left = int((COOLDOWN_SECONDS - (now - last)) // 60)
        await interaction.response.send_message(f"⏳ Подождите {left} мин. перед повторной игрой! (кулдаун 3 часа)", ephemeral=True)
        return False
    timestamps[key] = now
    save_timestamps(timestamps)
    return True

class Fun(commands.Cog):
    @app_commands.command(name="колесо", description="Использовать колесо фортуны из инвентаря")
    async def fortune_wheel_slash(self, interaction: discord.Interaction):
        user = interaction.user
        await self.client.db.inv.open_acc(user)
        await self.client.db.bank.open_acc(user)
        item_name = "<:68:1396933324789776484> колесо фортуны"
        quantity = await self.client.db.inv.update_acc(user, 0, item_name)
        if not quantity or quantity[0] < 1:
            await interaction.response.send_message("У вас нет колеса фортуны в инвентаре! Купите его в магазине.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        await self.client.db.inv.update_acc(user, -1, item_name)
        import random
        import io
        import asyncio
        # Шансы: Бесплатный CS — 80%, Титул — 1%, остальные — по 5%
        weights = [0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.80, 0.05, 0.05, 0.05, 0.01]
        stop_index = random.choices(range(11), weights=weights, k=1)[0]
        from wheel_of_fortune import SECTORS, make_glassmorphism_spin_gif
        buf = io.BytesIO()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: make_glassmorphism_spin_gif(stop_index=stop_index, frames=60, out_path=buf))
        file = discord.File(buf, filename="fortune_spin.gif")
        prize = SECTORS[stop_index]
        gold_map = {7: 10, 8: 100, 9: 1000}
        if stop_index in gold_map:
            amount = gold_map[stop_index]
            await self.client.db.bank.update_acc(user, +amount)
            await interaction.followup.send(f"Поздравляем! Вам выпало **{prize}** и зачислено {amount} <:gold:1396929958965940286>!", file=file)
        else:
            prize_map = {
                0: "<:proakk7:1397688074343026708> про акк 2 дня",
                1: "<:BTNSilence:1398024524330434773> анмут",
                2: "<:BTNAdvancedUnholyArmor:1402048051404869702> Ладдер армор 3 дня",
                3: "<:BTNAdvancedUnholyArmor:1402048051404869702> Ладдер армор 7 дней",
                4: "<:bonus:1402048692495585300> Ладдер бонус 3 дня",
                5: "<:bonus:1402048692495585300> Ладдер бонус 7 дней",
                6: "<:cs:1397687842779435068> бесплатный кс",
            }
            if stop_index == 10:
                await interaction.followup.send(f"Поздравляем! Вам выпал редкий приз: **{prize}**! Обратитесь к администрации для активации титула.", file=file)
            else:
                item = prize_map.get(stop_index)
                if item:
                    await self.client.db.inv.update_acc(user, +1, item)
                    await interaction.followup.send(f"Поздравляем! Вам выпал приз: **{prize}**. Предмет добавлен в ваш инвентарь!", file=file)
                else:
                    await interaction.followup.send(f"Вам выпал приз: **{prize}**. (Ошибка маппинга предмета)", file=file)

    def __init__(self, client: EconomyBot):
        self.client = client
        self.bank = self.client.db.bank
        self._load_dota_phrases()
        
    def _load_dota_phrases(self):
        import json
        try:
            with open('dota.json', 'r', encoding='utf-8') as f:
                self.dota_phrases = json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки dota.json: {e}")
            self.dota_phrases = ["Ошибка загрузки предсказаний"]

    @app_commands.command(name="дота", description="Получить предсказание для игры в iCCup")
    async def dota_slash(self, interaction: discord.Interaction):
        phrase = random.choice(self.dota_phrases)
        embed = discord.Embed(
            title="🎮 Предсказание для iCCup",
            description=phrase,
            color=discord.Color.purple()
        )
        embed.set_footer(text="Удачи в следующей катке!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="монетка", description="Подбросить монетку (орел/решка)")
    @app_commands.describe(bet_on="Орел или решка", amount="Сумма ставки")
    async def coin_slash(self, interaction: discord.Interaction, bet_on: str, amount: int):
        user = interaction.user
        if not await check_and_update_cooldown(interaction, "coin"):
            return
        await self.bank.open_acc(user)
        bet_on = "орел" if "о" in bet_on.lower() else "решка"
        if not 25 <= amount <= 150:
            await interaction.response.send_message("Ставка может быть только от 25 до 150 <:gold:1396929958965940286>", ephemeral=True)
            return
        users = await self.bank.get_acc(user)
        if users[1] < amount:
            await interaction.response.send_message("У вас недостаточно <:gold:1396929958965940286>", ephemeral=True)
            return
        import asyncio
        wait_msg = await interaction.response.send_message("Крутим монетку... 🪙", ephemeral=False)
        await asyncio.sleep(2)
        import random
        win = random.random() < 0.15
        if not win:
            await self.bank.update_acc(user, -amount)
            users = await self.bank.get_acc(user)
            embed = discord.Embed(title="Монетка: Проигрыш 😢", color=0xE74C3C)
            embed.add_field(name="Ставка", value=f"{amount} <:gold:1396929958965940286>")
            embed.add_field(name="Баланс", value=f"{users[1]} <:gold:1396929958965940286>")
            embed.set_footer(text="Удачи в следующий раз!")
            await interaction.edit_original_response(content=None, embed=embed)
            return
        reward = round(amount * 0.5)
        await self.bank.update_acc(user, +reward)
        users = await self.bank.get_acc(user)
        embed = discord.Embed(title="Монетка: Победа 🎉", color=0x2ECC71)
        embed.add_field(name="Ставка", value=f"{amount} <:gold:1396929958965940286>")
        embed.add_field(name="Выигрыш", value=f"{amount + reward} <:gold:1396929958965940286>")
        embed.add_field(name="Баланс", value=f"{users[1]} <:gold:1396929958965940286>")
        embed.set_footer(text="Поздравляем!")
        await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(name="слоты", description="Игровые слоты")
    @app_commands.describe(amount="Сумма ставки")
    async def slots_slash(self, interaction: discord.Interaction, amount: int):
        user = interaction.user
        if not await check_and_update_cooldown(interaction, "slots"):
            return
        await self.bank.open_acc(user)
        if not 25 <= amount <= 150:
            await interaction.response.send_message("Ставка может быть только от 25 до 150 <:gold:1396929958965940286>", ephemeral=True)
            return
        users = await self.bank.get_acc(user)
        if users[1] < amount:
            await interaction.response.send_message("У вас недостаточно <:gold:1396929958965940286>", ephemeral=True)
            return
        import asyncio
        import random as pyrand
        slot1 = ["💝", "🎉", "💎", "💵", "💰", "🚀", "🍿"]
        slot2 = ["💝", "🎉", "💎", "💵", "💰", "🚀", "🍿"]
        slot3 = ["💝", "🎉", "💎", "💵", "💰", "🚀", "🍿"]
        sep = " | "
        em = discord.Embed(description=f"| {sep.join(slot1[:3])} |\n| {sep.join(slot2[:3])} | 📍\n| {sep.join(slot3[:3])} |\n", color=0x95A5A6)
        msg = await interaction.response.send_message(content="Крутим слоты... 🎰", embed=em)
        await asyncio.sleep(2)
        s1 = pyrand.choice(slot1)
        s2 = pyrand.choice(slot2)
        s3 = pyrand.choice(slot3)
        slot_line = f"| {s1} | {s2} | {s3} |"
        import random
        win = random.random() < 0.15
        if win:
            reward = round(amount * 0.5)
            await self.bank.update_acc(user, +reward)
            users = await self.bank.get_acc(user)
            embed = discord.Embed(title="Слоты: Победа 🎉", description=slot_line, color=0x2ECC71)
            embed.add_field(name="Ставка", value=f"{amount} <:gold:1396929958965940286>")
            embed.add_field(name="Выигрыш", value=f"{amount + reward} <:gold:1396929958965940286>")
            embed.add_field(name="Баланс", value=f"{users[1]} <:gold:1396929958965940286>")
            embed.set_footer(text="Поздравляем!")
        else:
            await self.bank.update_acc(user, -amount)
            users = await self.bank.get_acc(user)
            embed = discord.Embed(title="Слоты: Проигрыш 😢", description=slot_line, color=0xE74C3C)
            embed.add_field(name="Ставка", value=f"{amount} <:gold:1396929958965940286>")
            embed.add_field(name="Баланс", value=f"{users[1]} <:gold:1396929958965940286>")
            embed.set_footer(text="Попробуйте ещё раз!")
        await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(name="кости", description="Играть в кости (1-6)")
    @app_commands.describe(amount="Сумма ставки", bet_on="Число (по умолчанию 6)")
    async def dice_slash(self, interaction: discord.Interaction, amount: int, bet_on: int = 6):
        user = interaction.user
        if not await check_and_update_cooldown(interaction, "dice"):
            return
        await self.bank.open_acc(user)
        if not 25 <= amount <= 150:
            await interaction.response.send_message("Ставка может быть только от 25 до 150 <:gold:1396929958965940286>", ephemeral=True)
            return
        users = await self.bank.get_acc(user)
        if users[1] < amount:
            await interaction.response.send_message("У вас недостаточно <:gold:1396929958965940286>", ephemeral=True)
            return
        import asyncio
        wait_msg = await interaction.response.send_message("Бросаем кости... 🎲", ephemeral=False)
        await asyncio.sleep(2)
        import random
        dice = random.randint(1, 6)
        win = dice == bet_on
        if win:
            reward = round(amount * 0.5)
            await self.bank.update_acc(user, +reward)
            users = await self.bank.get_acc(user)
            embed = discord.Embed(title="Кости: Победа 🎉", description=f"Выпало: {dice}", color=0x2ECC71)
            embed.add_field(name="Ставка", value=f"{amount} <:gold:1396929958965940286>")
            embed.add_field(name="Выигрыш", value=f"{reward} <:gold:1396929958965940286>")
            embed.add_field(name="Баланс", value=f"{users[1]} <:gold:1396929958965940286>")
            embed.set_footer(text="Поздравляем!")
        else:
            await self.bank.update_acc(user, -amount)
            users = await self.bank.get_acc(user)
            embed = discord.Embed(title="Кости: Проигрыш 😢", description=f"Выпало: {dice}", color=0xE74C3C)
            embed.add_field(name="Ставка", value=f"{amount} <:gold:1396929958965940286>")
            embed.add_field(name="Баланс", value=f"{users[1]} <:gold:1396929958965940286>")
            embed.set_footer(text="Попробуйте ещё раз!")
        await interaction.edit_original_response(content=None, embed=embed)


class BlackjackView(View):
    def __init__(self, ctx, player_hand, dealer_hand, bet, bank, message=None):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.bet = bet
        self.bank = bank
        self.message = message
        self.finished = False

    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.author

    @staticmethod
    def hand_value(hand):
        value = 0
        aces = 0
        for card in hand:
            if card[:-1] in ["J", "Q", "K"]:
                value += 10
            elif card[:-1] == "A":
                aces += 1
                value += 11
            else:
                value += int(card[:-1])
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value

    @staticmethod
    def hand_str(hand):
        return " ".join(hand)

    async def update_embed(self, result=None, color=0x2ECC71):
        embed = discord.Embed(title="Блэкджек /21 🂡", color=color)
        embed.add_field(name="Ваши карты", value=f"{self.hand_str(self.player_hand)}\nСумма: {self.hand_value(self.player_hand)}", inline=False)
        embed.add_field(name="Карты дилера", value=f"{self.hand_str([self.dealer_hand[0], '❓'])}", inline=False)
        embed.add_field(name="Ставка", value=f"{self.bet} <:gold:1396929958965940286>")
        embed.add_field(name="Баланс", value=f"{self.bank} <:gold:1396929958965940286>")
        if result:
            embed.add_field(name="Результат", value=result, inline=False)
        await self.message.edit(embed=embed, view=self if not self.finished else None)

    @discord.ui.button(label="Взять карту", style=discord.ButtonStyle.primary, custom_id="hit")
    async def hit(self, interaction: discord.Interaction, button: Button):
        card = pyrand.choice(self.ctx.bot.cards)
        self.player_hand.append(card)
        if self.hand_value(self.player_hand) > 21:
            self.finished = True
            await self.ctx.bot.bank.update_acc(self.ctx.author, -self.bet)
            users = await self.ctx.bot.bank.get_acc(self.ctx.author)
            await interaction.response.edit_message(embed=discord.Embed(title="Блэкджек /21 🂡", color=0xE74C3C)
                .add_field(name="Ваши карты", value=f"{self.hand_str(self.player_hand)}\nСумма: {self.hand_value(self.player_hand)}", inline=False)
                .add_field(name="Карты дилера", value=f"{self.hand_str(self.dealer_hand)}", inline=False)
                .add_field(name="Ставка", value=f"{self.bet} <:gold:1396929958965940286>")
                .add_field(name="Баланс", value=f"{users[1]} <:gold:1396929958965940286>")
                .add_field(name="Результат", value="Перебор! Вы проиграли 😢", inline=False), view=None)
        else:
            await self.update_embed()

    @discord.ui.button(label="Оставить", style=discord.ButtonStyle.secondary, custom_id="stand")
    async def stand(self, interaction: discord.Interaction, button: Button):
        self.finished = True
        # Открываем карты дилера
        while self.hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(pyrand.choice(self.ctx.bot.cards))
        player_val = self.hand_value(self.player_hand)
        dealer_val = self.hand_value(self.dealer_hand)
        users = await self.ctx.bot.bank.get_acc(self.ctx.author)
        if dealer_val > 21 or player_val > dealer_val:
            await self.ctx.bot.bank.update_acc(self.ctx.author, int(self.bet * 1.5))
            users = await self.ctx.bot.bank.get_acc(self.ctx.author)
            result = f"Вы выиграли! 🎉\nВыплата: {int(self.bet * 1.5)} <:gold:1396929958965940286>"
            color = 0x2ECC71
        elif player_val == dealer_val:
            result = "Ничья! Ваши деньги возвращены."
            color = 0xF1C40F
        else:
            await self.ctx.bot.bank.update_acc(self.ctx.author, -self.bet)
            users = await self.ctx.bot.bank.get_acc(self.ctx.author)
            result = f"Вы проиграли! 😢\nПотеря: {self.bet} <:gold:1396929958965940286>"
            color = 0xE74C3C
        embed = discord.Embed(title="Блэкджек /21 🂡", color=color)
        embed.add_field(name="Ваши карты", value=f"{self.hand_str(self.player_hand)}\nСумма: {player_val}", inline=False)
        embed.add_field(name="Карты дилера", value=f"{self.hand_str(self.dealer_hand)}\nСумма: {dealer_val}", inline=False)
        embed.add_field(name="Ставка", value=f"{self.bet} <:gold:1396929958965940286>")
        embed.add_field(name="Баланс", value=f"{users[1]} <:gold:1396929958965940286>")
        embed.add_field(name="Результат", value=result, inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

    @app_commands.command(name="21", description="Играть в блэкджек /21")
    async def blackjack(self, interaction: discord.Interaction, ставка: int):
        user = interaction.user
        if not await check_and_update_cooldown(interaction, "blackjack"):
            return
        await self.bank.open_acc(user)
        if not 25 <= ставка <= 150:
            return await interaction.response.send_message("Ставка может быть только от 25 до 150 <:gold:1396929958965940286>", ephemeral=True)
        users = await self.bank.get_acc(user)
        if users[1] < ставка:
            return await interaction.response.send_message("У вас недостаточно <:gold:1396929958965940286>", ephemeral=True)
        # Колода
        suits = ["♠", "♥", "♦", "♣"]
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        self.client.cards = [f"{r}{s}" for r in ranks for s in suits]
        pyrand.shuffle(self.client.cards)
        player_hand = [self.client.cards.pop(), self.client.cards.pop()]
        dealer_hand = [self.client.cards.pop(), self.client.cards.pop()]
        view = BlackjackView(interaction, player_hand, dealer_hand, ставка, users[1])
        embed = discord.Embed(title="Блэкджек /21 🂡", color=0x3498DB)
        embed.add_field(name="Ваши карты", value=f"{BlackjackView.hand_str(player_hand)}\nСумма: {BlackjackView.hand_value(player_hand)}", inline=False)
        embed.add_field(name="Карты дилера", value=f"{dealer_hand[0]} ❓", inline=False)
        embed.add_field(name="Ставка", value=f"{ставка} <:gold:1396929958965940286>")
        embed.add_field(name="Баланс", value=f"{users[1]} <:gold:1396929958965940286>")
        view.message = await interaction.response.send_message(embed=embed, view=view)


# if you are using 'discord.py >=v2.0' comment(remove) below code
# def setup(client):
#     client.add_cog(Fun(client))

# if you are using 'discord.py >=v2.0' uncomment(add) below code
async def setup(client):
    await client.add_cog(Fun(client))
