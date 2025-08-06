from base import EconomyBot

import discord

from discord.ext import commands
from discord import app_commands


class Shop(commands.Cog):
    def __init__(self, client: EconomyBot):
        self.client = client
        self.inv = self.client.db.inv

    class ShopView(discord.ui.View):
        def __init__(self, client):
            super().__init__(timeout=None)
            self.client = client

        @discord.ui.button(label="Мой инвентарь", style=discord.ButtonStyle.secondary, custom_id="inventory")
        async def show_inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                inventory_cog = self.client.get_cog("Inventory")
                if inventory_cog:
                    await inventory_cog.show_inventory(interaction)
                else:
                    await interaction.response.send_message("Команда временно недоступна", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"Произошла ошибка: {str(e)}", ephemeral=True)

        @discord.ui.button(label="Моя статистика", style=discord.ButtonStyle.secondary, custom_id="stats")
        async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                activity_cog = self.client.get_cog("Activity")
                if activity_cog and hasattr(activity_cog, "статистика_slash"):
                    # Вызываем метод напрямую, member=None (текущий пользователь)
                    await activity_cog.статистика_slash(interaction)
                else:
                    await interaction.response.send_message("Команда статистики временно недоступна", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"Произошла ошибка: {str(e)}", ephemeral=True)

   

    @app_commands.command(name="магазин", description="Показать магазин предметов")
    async def shop_slash(self, interaction: discord.Interaction):
        user = interaction.user
        await self.inv.open_acc(user)
        em = discord.Embed(
            title="МАГАЗИН",
            color=discord.Color(0x00ff00)
        )
        max_fields = 24
        for item in self.inv.shop_items[:max_fields]:
            name = item["name"]
            cost = item["cost"]
            item_id = item["id"]
            item_info = item["info"]
            em.add_field(
                name="\u200b", # пустое имя, чтобы всё было в value
                value=f"**{name}** — {cost} <:gold:1396929958965940286>\n{item_info} (ID: `{item_id}`)",
                inline=False
            )
        if len(self.inv.shop_items) > max_fields:
            em.set_footer(text=f"Показаны только первые {max_fields} товаров. Для остальных используйте поиск или пагинацию.")
        # Создаем view с кнопками
        view = self.ShopView(self.client)
        await interaction.response.send_message(embed=em, view=view)

    @app_commands.command(name="магазин_инфо", description="Информация о предмете магазина")
    @app_commands.describe(item_name="Название предмета")
    async def shop_info_slash(self, interaction: discord.Interaction, item_name: str):
        for item in self.inv.shop_items:
            name = item["name"]
            cost = item["cost"]
            item_info = item["info"]
            if name == item_name:
                em = discord.Embed(
                    description=item_info,
                    title=f"{name.upper()}"
                )
                sell_amt = int(cost / 4)
                em.add_field(name="Цена покупки", value=f"{cost} <:gold:1396929958965940286>", inline=False)
                em.add_field(name="Цена продажи",
                             value=f"{sell_amt} <:gold:1396929958965940286>", inline=False)
                await interaction.response.send_message(embed=em)
                return
        await interaction.response.send_message(f"Нет предмета с названием '{item_name}'", ephemeral=True)


# if you are using 'discord.py >=v2.0' comment(remove) below code
# def setup(client):
#     client.add_cog(Shop(client))

# if you are using 'discord.py >=v2.0' uncomment(add) below code
async def setup(client):
    await client.add_cog(Shop(client))
