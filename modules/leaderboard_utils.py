import discord
from datetime import datetime
import pytz

def get_medal_emoji(position: int) -> str:
    """Возвращает эмодзи медали для указанной позиции"""
    medals = {
        1: "🥇",
        2: "🥈",
        3: "🥉"
    }
    return medals.get(position, "👑")

def format_balance(amount: int) -> str:
    """Форматирует сумму с разделителями"""
    return f"{amount:,}".replace(",", ".")

def get_moscow_time():
    """Получить текущее время по МСК"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)

async def create_balance_leaderboard_embed(users_data, client):
    """
    Создает красивый embed для топа по балансу
    users_data: список кортежей (user_id, total_balance)
    """
    moscow_time = get_moscow_time()
    current_date = moscow_time.strftime("%d.%m.%Y")
    
    embed = discord.Embed(
        title="💰 Топ 10 богачей сервера 💰",
        color=0x2F3136  # Discord dark grey
    )
    
    description = []
    for i, (user_id, total) in enumerate(users_data[:10], 1):
        medal = get_medal_emoji(i)
        member = client.get_guild(614513381600264202).get_member(user_id)
        if member:
            # Форматируем строку с балансом
            balance_str = format_balance(total)
            description.append(
                f"{medal} **#{i}** · {member.mention}\n"
                f"┗━ {balance_str} <:gold:1396897616729735299>\n"
            )
    
    if description:
        embed.description = "\n".join(description)
    else:
        embed.description = "*Список пуст*"
    
    # Добавляем время обновления
    embed.set_footer(
        text=f"Обновлено {moscow_time.strftime('%H:%M:%S')}",
        icon_url="https://cdn.discordapp.com/emojis/1396897616729735299.png"
    )
    
    return embed

def create_balance_buttons():
    """Создает кнопки для взаимодействия с топом"""
    buttons = discord.ui.View()
    
    # Кнопка магазина
    shop_button = discord.ui.Button(
        style=discord.ButtonStyle.secondary,
        label="Магазин",
        custom_id="shop"
    )
    buttons.add_item(shop_button)
    
    # Кнопка профиля
    profile_button = discord.ui.Button(
        style=discord.ButtonStyle.secondary,
        label="Профиль",
        custom_id="profile"
    )
    buttons.add_item(profile_button)
    
    # Кнопка развлечений
    fun_button = discord.ui.Button(
        style=discord.ButtonStyle.secondary,
        label="Развлечения",
        custom_id="fun"
    )
    buttons.add_item(fun_button)
    
    return buttons
