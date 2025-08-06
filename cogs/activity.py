from base import EconomyBot
from discord import app_commands
from discord.ext import commands
import discord
import random
from datetime import datetime, timedelta
import json
import os
import asyncio
from modules.ext import send_or_update_voice_leaderboard_message
from modules.leaderboard_utils import get_medal_emoji  # Импорт функции для медалей
from modules.bank_funcs import TABLE_NAME  # Импорт имени таблицы из bank_funcs

# Константы для наград
VOICE_REWARD_PER_MINUTE = 1  # монет за минуту в голосовом канале
MESSAGE_REWARD = 1  # монет за сообщение
MIN_WORDS_FOR_REWARD = 2  # минимум слов в сообщении для награды
SERVER_ID = 614513381600264202  # ID вашего сервера
from collections import defaultdict
import pytz

BAN_FILE = 'bans.json'
STATS_FILE = 'stats.json'

# ID канала, где будет отображаться топ голосового чата
VOICE_TOP_CHANNEL_ID = 1399452236354027570  # Замените на ID вашего канала

VOICE_LEADERBOARD_MESSAGE_ID_FILE = "voice_leaderboard_message_id.txt"

VOICE_REWARD_PER_MINUTE = 1  # Сколько голды за минуту
VOICE_CHECK_INTERVAL = 60  # секунд

def load_bans():
    if not os.path.exists(BAN_FILE):
        return {}
    with open(BAN_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {}
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_moscow_time():
    """Получить текущее время по МСК"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)

def should_reset_stats():
    """Проверяет, нужно ли сбросить статистику (4 утра по МСК)"""
    moscow_time = get_moscow_time()
    return moscow_time.hour == 4 and moscow_time.minute == 0

class Activity(commands.Cog):
    def __init__(self, client: EconomyBot):
        self.client = client
        self.bank = self.client.db.bank
        self.voice_sessions = {}  # user_id: {'channel_id': int, 'joined_at': datetime}
        self.voice_reward_task = self.client.loop.create_task(self.voice_reward_loop())
        print("Запущен voice_reward_loop")
        self.voice_leaderboard_task = self.client.loop.create_task(self.voice_leaderboard_updater())
        print("Запущен voice_leaderboard_updater")
        self.stats = self.load_stats()
        print(f"Загружена статистика: {len(self.stats)} записей")
        
        # Инициализируем last_reset_date и проверяем необходимость сброса
        moscow_time = get_moscow_time()
        self.last_reset_date = moscow_time.date()
        
        # Проверяем, нужно ли сбросить статистику при запуске
        self.check_and_reset_stats_on_startup()
        
        self.client.loop.create_task(self.initialize_voice_sessions())
        self.client.loop.create_task(self.daily_reset_checker())

    def check_and_reset_stats_on_startup(self):
        """Проверяет и сбрасывает статистику при запуске бота, если прошло больше дня"""
        moscow_time = get_moscow_time()
        current_date = moscow_time.date()
        
        # Проверяем, есть ли данные о последнем сбросе
        last_reset_file = "last_reset_date.txt"
        if os.path.exists(last_reset_file):
            try:
                with open(last_reset_file, 'r') as f:
                    last_reset_str = f.read().strip()
                    if last_reset_str:
                        last_reset_date = datetime.strptime(last_reset_str, "%Y-%m-%d").date()
                        # Если прошло больше дня с последнего сброса, сбрасываем статистику
                        if (current_date - last_reset_date).days > 0:
                            print(f"Прошло больше дня с последнего сброса. Сбрасываем статистику.")
                            self.reset_daily_stats()
                            self.last_reset_date = current_date
                            # Сохраняем новую дату сброса
                            with open(last_reset_file, 'w') as f:
                                f.write(current_date.strftime("%Y-%m-%d"))
            except Exception as e:
                print(f"Ошибка при проверке даты сброса: {e}")
        else:
            # Если файл не существует, создаем его с текущей датой
            with open(last_reset_file, 'w') as f:
                f.write(current_date.strftime("%Y-%m-%d"))

    async def daily_reset_checker(self):
        """Проверяет необходимость сброса статистики в 4 утра по МСК"""
        await self.client.wait_until_ready()
        while True:
            try:
                moscow_time = get_moscow_time()
                current_date = moscow_time.date()
                
                # Если дата изменилась и сейчас 4 утра, сбрасываем статистику
                if (self.last_reset_date != current_date and 
                    moscow_time.hour == 4 and moscow_time.minute == 0):
                    
                    print(f"Сброс статистики голосовых чатов в {moscow_time}")
                    self.reset_daily_stats()
                    self.last_reset_date = current_date
                    
            except Exception as e:
                print(f"Ошибка в daily_reset_checker: {e}")
            
            # Проверяем каждую минуту
            await asyncio.sleep(60)

    def reset_daily_stats(self):
        """Сбрасывает ежедневную статистику голосовых чатов"""
        for user_id in self.stats:
            if "voice_minutes" in self.stats[user_id]:
                self.stats[user_id]["voice_minutes"] = 0
                self.stats[user_id]["voice_gold"] = 0
                self.stats[user_id]["voice_enter"] = None
        self.save_stats()
        
        # Сохраняем дату сброса
        moscow_time = get_moscow_time()
        current_date = moscow_time.date()
        with open("last_reset_date.txt", 'w') as f:
            f.write(current_date.strftime("%Y-%m-%d"))
        
        print("Статистика голосовых чатов сброшена")

    async def initialize_voice_sessions(self):
        await self.client.wait_until_ready()
        guild = self.client.get_guild(614513381600264202)
        now = datetime.utcnow()
        if guild:
            # Проверяем все голосовые каналы на сервере
            for channel in guild.voice_channels:
                for member in channel.members:
                    if not member.bot:
                        self.voice_sessions[str(member.id)] = {
                            'channel_id': channel.id,
                            'joined_at': now
                        }
                        # Обновляем время входа в статистику
                        self.update_stats(member.id, "voice_enter", now.timestamp())

    def load_voice_leaderboard_message_id(self):
        if os.path.exists(VOICE_LEADERBOARD_MESSAGE_ID_FILE):
            with open(VOICE_LEADERBOARD_MESSAGE_ID_FILE, "r") as f:
                return f.read().strip()
        return None

    def save_voice_leaderboard_message_id(self, message_id):
        with open(VOICE_LEADERBOARD_MESSAGE_ID_FILE, "w") as f:
            f.write(str(message_id))

    def load_stats(self):
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_stats(self):
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)

    async def voice_leaderboard_updater(self):
        """Автоматическое обновление топа голосового чата"""
        await self.client.wait_until_ready()
        
        while not self.client.is_closed():
            try:
                now = datetime.utcnow()
                moscow_time = get_moscow_time()
                leaderboard = []
                guild = self.client.get_guild(SERVER_ID)
                
                if not guild:
                    print(f"Не удалось найти сервер с ID {SERVER_ID}")
                    await asyncio.sleep(60)
                    continue

                # Собираем статистику
                for user_id, data in self.stats.items():
                    try:
                        # Базовая статистика из stats.json
                        voice_minutes = data.get("voice_minutes", 0)
                        voice_gold = data.get("voice_gold", 0)
                        
                        # Проверяем текущую сессию
                        session = self.voice_sessions.get(str(user_id))  # Убедимся что user_id это строка
                        if session and 'joined_at' in session:
                            # Рассчитываем время текущей сессии
                            time_spent = (now - session['joined_at']).total_seconds()
                            current_minutes = int(time_spent // 60)
                            if current_minutes > 0:
                                # Обновляем статистику пользователя
                                voice_minutes = current_minutes  # Используем текущее время сессии
                                voice_gold = current_minutes * VOICE_REWARD_PER_MINUTE

                        if voice_minutes > 0:  # Показываем только активных пользователей
                            member = guild.get_member(int(user_id))
                            if member:
                                name = f"<@{user_id}>"  # Используем только упоминание пользователя
                                leaderboard.append({
                                    "name": name,
                                    "minutes": voice_minutes,
                                    "gold": voice_gold
                                })
                    except Exception as e:
                        print(f"Ошибка при обработке пользователя {user_id} в топе: {e}")
                        continue

                # Сортируем и берем топ-10
                leaderboard.sort(key=lambda x: x["minutes"], reverse=True)
                top10 = leaderboard[:10]

                if not top10:
                    print("Нет активных пользователей для отображения в топе")
                    await asyncio.sleep(60)
                    continue

                # Формируем embed сообщение
                title = f"🎙️ **Топ-10 активных в голосовых каналах за {moscow_time.strftime('%d.%m.%Y')}** 🎙️"
                description = []
                
                for i, entry in enumerate(top10, 1):
                    medal = get_medal_emoji(i)  # 🥇, 🥈, 🥉 для топ-3
                    description.append(
                        f"\n{medal} **#{i}** · {entry['name']}\n"
                        f"⌛ {entry['minutes']} мин. ({entry['gold']} <:gold:1396897616729735299>)"
                    )

                # Учитываем часовой пояс Москвы
                moscow_timestamp = int(moscow_time.timestamp())
                
                full_description = title + "\n" + "\n".join(description)
                full_description += f"\n\n⏰ **Обновлено**: <t:{moscow_timestamp}:R>"

                embed = discord.Embed(
                    description=full_description,
                    color=0x2F3136,  # Discord dark theme color
                    timestamp=moscow_time  # Добавляем временную метку в сам эмбед
                )

                try:
                    # Получаем канал для топа
                    channel = self.client.get_channel(VOICE_TOP_CHANNEL_ID)
                    if not channel:
                        print(f"Канал {VOICE_TOP_CHANNEL_ID} не найден")
                        await asyncio.sleep(60)
                        continue
                    
                    # Проверяем права бота в канале
                    permissions = channel.permissions_for(channel.guild.me)
                    if not permissions.send_messages or not permissions.embed_links:
                        print(f"У бота нет прав для отправки сообщений или эмбедов в канале {channel.name}")
                        await asyncio.sleep(60)
                        continue
                        
                    print(f"Попытка обновить/создать сообщение топа в канале {channel.name}")
                    # Пытаемся получить существующее сообщение
                    message_id = self.load_voice_leaderboard_message_id()
                    if message_id:
                        try:
                            message = await channel.fetch_message(int(message_id))
                            await message.edit(embed=embed)
                            print(f"Обновлено сообщение топа {message.id}")
                        except:
                            # Если сообщение не найдено, отправляем новое
                            new_message = await channel.send(embed=embed)
                            self.save_voice_leaderboard_message_id(str(new_message.id))
                            print(f"Создано новое сообщение топа {new_message.id}")
                    else:
                        # Первая отправка
                        new_message = await channel.send(embed=embed)
                        self.save_voice_leaderboard_message_id(str(new_message.id))
                        print(f"Создано первое сообщение топа {new_message.id}")

                except Exception as e:
                    print(f"Ошибка при отправке/обновлении сообщения топа: {e}")

            except Exception as e:
                print(f"Общая ошибка в voice_leaderboard_updater: {e}")

            await asyncio.sleep(60)

    async def give_voice_reward(self, member, minutes):
        user_id = str(member.id)
        gold = minutes * VOICE_REWARD_PER_MINUTE
        await self.bank.open_acc(member)
        await self.bank.update_acc(member, gold)
        # Обновляем stats
        if user_id not in self.stats:
            self.stats[user_id] = {"voice_minutes": 0, "voice_gold": 0, "messages": 0, "message_gold": 0}
        self.stats[user_id]["voice_minutes"] += minutes
        self.stats[user_id]["voice_gold"] += gold
        self.save_stats()

    def update_stats(self, user_id, key, value):
        user_id = str(user_id)
        if user_id not in self.stats:
            self.stats[user_id] = {"voice_minutes": 0, "voice_gold": 0, "messages": 0, "message_gold": 0, "voice_enter": None}
        if key == "voice_enter":
            self.stats[user_id][key] = value
        else:
            self.stats[user_id][key] += value
        self.save_stats()  # Используем метод класса

    @commands.Cog.listener()
    async def on_message(self, message):
        # Игнорировать сообщения не с нужного сервера и личные сообщения
        if message.guild is None or message.guild.id != SERVER_ID:
            return
        if message.author.bot:
            return
        # Проверяем минимальное количество слов
        if len(message.content.split()) < MIN_WORDS_FOR_REWARD:
            return
            
        # Проверка на бан
        bans = load_bans()
        uid = str(message.author.id)
        now = datetime.utcnow()
        if uid in bans:
            until = bans[uid]["until"]
            if now.timestamp() < until:
                return
            else:
                bans.pop(uid)
                with open(BAN_FILE, 'w', encoding='utf-8') as f:
                    json.dump(bans, f, ensure_ascii=False, indent=2)
                    
        # Начисление награды за сообщение
        try:
            result = await self.bank.update_acc(message.author, MESSAGE_REWARD, mode="wallet")
            if result is not None:
                self.update_stats(message.author.id, "messages", 1)
                self.update_stats(message.author.id, "message_gold", MESSAGE_REWARD)
                print(f"Начислено {MESSAGE_REWARD} монет пользователю {message.author.name} за сообщение. Новый баланс: {result[0]}")
        except Exception as e:
            print(f"Ошибка при начислении награды за сообщение: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        
        # Проверяем только нужный сервер
        if member.guild.id != SERVER_ID:
            return
            
        # Проверка на бан
        bans = load_bans()
        uid = str(member.id)
        now = datetime.utcnow()
        if uid in bans:
            until = bans[uid]["until"]
            if now.timestamp() < until:
                return
            else:
                bans.pop(uid)
                with open(BAN_FILE, 'w', encoding='utf-8') as f:
                    json.dump(bans, f, ensure_ascii=False, indent=2)
                    
        try:
            # Проверяем, не афк ли канал
            if after.channel and member.guild.afk_channel and after.channel.id == member.guild.afk_channel.id:
                return
                
            # Если пользователь глушит микрофон или наушники, игнорируем
            if before.channel == after.channel:
                return
                
        except Exception as e:
            print(f"Ошибка при проверке состояния канала: {e}")
            return
        
        # Вошёл в голосовой канал
        if before.channel is None and after.channel is not None:
            self.voice_sessions[str(member.id)] = {
                'channel_id': after.channel.id,
                'joined_at': now
            }
            # Сохраняем время входа в stats.json
            self.update_stats(member.id, "voice_enter", now.timestamp())
            self.client.loop.create_task(self.check_voice_inactive(member, after.channel))
        
        # Вышел из голосового канала
        elif before.channel is not None and after.channel is None:
            # Получаем время входа из stats.json
            stats = self.stats.get(str(member.id), {})
            enter_ts = stats.get("voice_enter")
            if enter_ts:
                start = datetime.utcfromtimestamp(enter_ts)
                minutes = int((now - start).total_seconds() // 60)
                if minutes > 0:
                    reward = minutes * VOICE_REWARD_PER_MINUTE
                    result = await self.bank.update_acc(member, reward, mode="wallet")
                    if result is not None:
                        self.update_stats(member.id, "voice_minutes", minutes)
                        self.update_stats(member.id, "voice_gold", reward)
                        print(f"Начислено {reward} монет пользователю {member.name} при выходе из канала. Новый баланс: {result[0]}")
            # Очищаем время входа
            self.update_stats(member.id, "voice_enter", None)
            self.voice_sessions.pop(str(member.id), None)
        
        # Перемещение между каналами
        elif before.channel is not None and after.channel is not None:
            # Обновляем время входа для нового канала
            self.voice_sessions[str(member.id)] = {
                'channel_id': after.channel.id,
                'joined_at': now
            }
            self.update_stats(member.id, "voice_enter", now.timestamp())

    async def check_voice_inactive(self, member, channel):
        await asyncio.sleep(300)  # 5 минут
        last = self.voice_sessions.get(str(member.id))
        if not last:
            return  # Уже вышел
        now = datetime.utcnow()
        if (now - last['joined_at']).total_seconds() >= 600:
            try:
                await member.move_to(None, reason="Неактивность в голосовом канале 5 минут")
                self.voice_sessions.pop(str(member.id), None)
                await channel.guild.system_channel.send(f"{member.display_name} был кикнут из войса за неактивность 5 минут.")
            except Exception:
                pass
                
    async def voice_reward_loop(self):
        """Периодически начисляет награды за голосовой чат"""
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            try:
                now = datetime.utcnow()
                
                for user_id, session in list(self.voice_sessions.items()):  # Используем list() для безопасного изменения словаря
                    try:
                        member = self.client.get_guild(SERVER_ID).get_member(int(user_id))
                        if not member:
                            self.voice_sessions.pop(user_id, None)
                            continue

                        # Проверяем, находится ли пользователь все еще в голосовом канале
                        voice_state = member.voice
                        if not voice_state or not voice_state.channel:
                            self.voice_sessions.pop(user_id, None)
                            continue

                        # Проверяем AFK статус и канал
                        if voice_state.afk:
                            self.voice_sessions.pop(user_id, None)
                            continue

                        # Проверка на AFK канал
                        guild = member.guild
                        if guild and guild.afk_channel and voice_state.channel and voice_state.channel.id == guild.afk_channel.id:
                            self.voice_sessions.pop(user_id, None)
                            continue

                        # Проверяем, не замучен/заглушен ли пользователь
                        if voice_state.self_mute or voice_state.self_deaf:
                            self.voice_sessions.pop(user_id, None)
                            continue

                        # Сначала обновляем время
                        self.update_stats(member.id, "voice_minutes", 1)
                        # Затем начисляем награду на основе времени
                        reward = VOICE_REWARD_PER_MINUTE
                        result = await self.bank.update_acc(member, reward, mode="wallet")
                        if result is not None:
                            self.update_stats(member.id, "voice_gold", reward)
                            # Обновляем глобальную статистику
                            await self.bank._db.run(
                                f"UPDATE `{TABLE_NAME}` SET total_voice_minutes = total_voice_minutes + 1, "
                                f"total_voice_gold = total_voice_gold + ? WHERE userID = ?",
                                (reward, member.id)
                            )
                            print(f"Начислено {reward} монет пользователю {member.name} за минуту в голосовом канале. Новый баланс: {result[0]}")
                        
                    except Exception as e:
                        print(f"Ошибка при обработке пользователя {user_id} в voice_reward_loop: {e}")
                        continue
                        
            except Exception as e:
                print(f"Ошибка в цикле наград за голос: {e}")
            
            await asyncio.sleep(60)  # Ждем 1 минуту


    @app_commands.command(name="статистика", description="Показать статистику пользователя")
    async def статистика_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        print(f"DEBUG: Слэш-команда 'статистика' вызвана пользователем {interaction.user.name}")
        user = member or interaction.user
        await self.bank.open_acc(user)
        data = await self.bank.get_acc(user)
        if not data:
            print(f"DEBUG: Ошибка получения данных для {user.name}")
            await interaction.response.send_message("Ошибка при получении статистики", ephemeral=True)
            return
        user_id = str(user.id)
        daily_stats = self.stats.get(user_id, {"voice_minutes": 0, "voice_gold": 0, "messages": 0, "message_gold": 0, "voice_enter": None})
        now = datetime.utcnow()
        current_session_minutes = 0
        session = self.voice_sessions.get(user_id)
        if session:
            joined_at = session['joined_at']
            current_session_minutes = int((now - joined_at).total_seconds() // 60)
        daily_voice_minutes = daily_stats["voice_minutes"] + current_session_minutes
        embed = discord.Embed(title=f"Статистика {user.display_name} ⏣", color=discord.Color.green())
        embed.add_field(
            name="📊 Сегодня",
            value=f"🕐 Время в войсе: {daily_voice_minutes} мин + {daily_stats['voice_gold']} <:gold:1396897616729735299>\n"
                  f"💬 Сообщений: {daily_stats['messages']} + {daily_stats['message_gold']} <:gold:1396897616729735299>",
            inline=False
        )
        embed.add_field(
            name="🏆 За все время",
            value=f"🕐 Время в войсе: {data[3]} мин + {data[4]} <:gold:1396897616729735299>\n"
                  f"💬 Сообщений: {data[5]} + {data[6]} <:gold:1396897616729735299>",
            inline=False
        )
        print(f"DEBUG: Отправляем ответ для {user.name}")
        await interaction.response.send_message(embed=embed, ephemeral=False)


    @app_commands.command(name="сброс_статистики", description="Сбросить статистику голосовых чатов (только для администраторов)")
    async def reset_stats_slash(self, interaction: discord.Interaction):
        """Слэш-команда для сброса статистики (только для админов)"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("⛔ Только для администраторов!", ephemeral=True)
            return
        print(f"DEBUG: Слэш-команда 'сброс_статистики' вызвана пользователем {interaction.user.name}")
        self.reset_daily_stats()
        await interaction.response.send_message("✅ Статистика голосовых чатов сброшена!", ephemeral=False)


    @app_commands.command(name="войс_сессии", description="Показать текущие голосовые сессии (только для администраторов)")
    async def voice_sessions_slash(self, interaction: discord.Interaction):
        """Слэш-команда для просмотра текущих голосовых сессий (только для админов)"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("⛔ Только для администраторов!", ephemeral=True)
            return
        print(f"DEBUG: Слэш-команда 'войс_сессии' вызвана пользователем {interaction.user.name}")
        if not self.voice_sessions:
            await interaction.response.send_message("Нет активных голосовых сессий", ephemeral=True)
            return
        now = datetime.utcnow()
        description = "Активные голосовые сессии:\n\n"
        guild = interaction.guild
        for user_id, session in self.voice_sessions.items():
            member = guild.get_member(int(user_id)) if guild else None
            if member:
                channel = guild.get_channel(session['channel_id']) if guild else None
                duration = int((now - session['joined_at']).total_seconds() // 60)
                description += f"{member.display_name}:\n"
                description += f"Канал: {channel.name if channel else 'Неизвестно'}\n"
                description += f"Время: {duration} мин.\n\n"
        embed = discord.Embed(title="Статус голосовых сессий", description=description, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=False)

async def setup(client):
    await client.add_cog(Activity(client))