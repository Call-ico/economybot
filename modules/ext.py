import aiosqlite
import aiohttp
from typing import Optional, Any, Tuple
from modules.config import TOKEN, APPLICATION_ID
from datetime import datetime
import pytz
import asyncio

VOICE_CHANNEL_ID = 1399452236354027570  # I     D канала для голосового топа
MESSAGE_ID_FILE = "voice_leaderboard_message_id.txt"


class Database:
    def __init__(self, db_name: str):
        self.db_name = db_name

    @staticmethod
    async def _fetch(cursor: aiosqlite.Cursor, mode: str) -> Optional[Any]:
        if mode == "one":
            return await cursor.fetchone()
        if mode == "many":
            return await cursor.fetchmany()
        if mode == "all":
            return await cursor.fetchall()

        return None

    async def connect(self) -> aiosqlite.Connection:
        """
        creates a new connection to the database.
        """

        return await aiosqlite.connect(self.db_name)

    async def execute(
        self, query: str, values: Tuple = (), *, fetch: str = None, commit: bool = False,
        conn: aiosqlite.Connection = None
    ) -> Optional[Any]:
        """
        runs the query without committing any changes to the database if `commit` is not passed at func call.

        Tip: use this method for fetching like:`SELECT` queries.

        :param query: SQL query.
        :param values: values to be passed to the query.
        :param fetch: Takes ('one', 'many', 'all').
        :param commit: Commits the changes to the database if it's set to `True`.
        :param conn: pass the new connection to execute two or more methods. If passed, you've to close it manually.
        :return: required data.
        """

        bypass = conn
        conn = await self.connect() if conn is None else conn
        cursor = await conn.cursor()

        await cursor.execute(query, values)
        if fetch is not None:
            data = await self._fetch(cursor, fetch)
        else:
            data = None

        if commit:
            await conn.commit()

        await cursor.close()
        if bypass is None:
            await conn.close()

        return data

    async def run(self, query: str, values: Tuple = (), *, conn: aiosqlite.Connection = None) -> None:
        """
        runs the query and commits any changes to the database directly.

        Tip: use this method if you want to commit changes to the database. Like: `CREATE, UPDATE, INSERT, DELETE`, etc.

        :param query: SQL query
        :param values: values to be passed to the query.
        :param conn: pass the new connection to execute two or more methods. If passed, you've to close it manually.
        """

        await self.execute(query, values, commit=True, conn=conn)


def format_time(minutes):
    """Форматирует время в часы и минуты"""
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours} ч., {mins} мин."
    else:
        return f"{mins} мин."


def get_medal_emoji(position):
    """Возвращает эмодзи медали для позиции"""
    medals = {
        1: "🥇",
        2: "🥈", 
        3: "🥉"
    }
    return medals.get(position, "👑")


def get_moscow_time():
    """Получить текущее время по МСК"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)


async def send_or_update_voice_leaderboard_message(top_data, message_id=None):
    """
    top_data: list of dicts: [{"name": str, "minutes": int, "gold": int}]
    message_id: str or None
    """
    # Получаем текущую дату по МСК
    moscow_time = get_moscow_time()
    current_date = moscow_time.strftime("%d.%m.%Y")
    current_timestamp = int(moscow_time.timestamp())
    
    # Формируем заголовок
    title = f"🎙️ **Топ-10 активных в голосовых каналах за {current_date}** 🎙️"
    
    # Формируем список участников
    leaderboard_lines = []
    for i, user in enumerate(top_data, 1):
        medal = get_medal_emoji(i)
        time_str = format_time(user['minutes'])
        gold_amount = user['gold']
        
        # Используем имя пользователя как есть (оно уже содержит mention или display_name)
        user_mention = user['name']
        
        line = f"\n{medal} #{i}. **{user_mention}** — {time_str} (+{gold_amount} <:mp:1155562128544108614>)"
        leaderboard_lines.append(line)
    
    # Формируем полное описание с разделителями
    description = title + "".join(leaderboard_lines) + f"\n\n⏰ **Обновлено**: <t:{current_timestamp}:R>"
    
    # Создаем embed с серой обводкой
    embed = {
        "title": "",
        "description": description,
        "color": 0x2F3136,  # Discord dark grey
        "type": "rich"
    }
    
    # Кнопки
    components = [
        {
            "type": 1,  # ActionRow
            "components": [
                {"type": 2, "style": 2, "label": "Магазин", "custom_id": "shop"},
                {"type": 2, "style": 2, "label": "Развлечения", "custom_id": "fun"},
                {"type": 2, "style": 2, "label": "Топ", "custom_id": "top"}
            ]
        }
    ]
    
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "embeds": [embed],
        "components": components
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            if message_id:
                # Пытаемся обновить существующее сообщение
                url = f"https://discord.com/api/v10/channels/{VOICE_CHANNEL_ID}/messages/{message_id}"
                async with session.patch(url, headers=headers, json=payload) as response:
                    if response.status == 404:
                        # Сообщение не найдено, создаем новое
                        url = f"https://discord.com/api/v10/channels/{VOICE_CHANNEL_ID}/messages"
                        async with session.post(url, headers=headers, json=payload) as new_response:
                            if new_response.status in [200, 201]:
                                data = await new_response.json()
                                return data["id"]
                            else:
                                error_text = await new_response.text()
                                print(f"Discord API error (new message): {new_response.status} {error_text}")
                                return None
                    elif response.status == 200:
                        # Сообщение успешно обновлено
                        data = await response.json()
                        return data["id"]
                    else:
                        error_text = await response.text()
                        print(f"Discord API error (update): {response.status} {error_text}")
                        return None
            else:
                # Создаем новое сообщение
                url = f"https://discord.com/api/v10/channels/{VOICE_CHANNEL_ID}/messages"
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status in [200, 201]:
                        data = await response.json()
                        return data["id"]
                    else:
                        error_text = await response.text()
                        print(f"Discord API error (create): {response.status} {error_text}")
                        return None
    except Exception as e:
        print(f"Ошибка при отправке сообщения в Discord: {e}")
        return None