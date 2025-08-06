# --- Импорты ---
import discord
from discord.ext import commands
from discord import app_commands
from modules.config import TOKEN
from pparser import fetch_iccup_stats, parse_game_data_async
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import aiofiles
import os
from bs4 import BeautifulSoup
from io import BytesIO
from typing import Optional, Dict, Tuple
import hashlib
import time


# --- Инициализация ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree



# Кэш изображении
class ImageCache:
    def __init__(self, max_size: int = 5000, expire_time: int = 9200):

        self.cache: Dict[str, Tuple[bytes, float]] = {}  # url_hash -> (image_data, timestamp)
        self.max_size = max_size
        self.expire_time = expire_time

    def _get_url_hash(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def _cleanup_expired(self):
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if current_time - timestamp > self.expire_time
        ]
        for key in expired_keys:
            del self.cache[key]

    def _cleanup_excess(self):
        if len(self.cache) > self.max_size:
            # Сортируем по времени и удаляем самые старые
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1][1])
            items_to_remove = len(self.cache) - self.max_size
            for i in range(items_to_remove):
                del self.cache[sorted_items[i][0]]

    def get(self, url: str) -> Optional[bytes]:
        if not url:
            return None

        url_hash = self._get_url_hash(url)

        if url_hash in self.cache:
            image_data, timestamp = self.cache[url_hash]
            if time.time() - timestamp <= self.expire_time:
                return image_data
            else:
                del self.cache[url_hash]

        return None

    def put(self, url: str, image_data: bytes):
        if not url or not image_data:
            return

        self._cleanup_expired()
        url_hash = self._get_url_hash(url)
        self.cache[url_hash] = (image_data, time.time())
        self._cleanup_excess()

    def clear(self):
        self.cache.clear()

    def get_stats(self) -> Dict[str, int]:
        return {
            "total_items": len(self.cache),
            "max_size": self.max_size,
            "expire_time": self.expire_time
        }


# Создаем глобальный экземпляр кэша
image_cache = ImageCache(max_size=5000, expire_time=9200)  # 3 час



def draw_k_on_image(k_value, bg_path="ui.png", result_path="result.png", font_path="arial.ttf"):
    try:
        bg = Image.open(bg_path).convert("RGBA")  # исправлено
        draw = ImageDraw.Draw(bg)

        try:
            font = ImageFont.truetype(font_path, size=36)  # исправлено
        except IOError:
            print("? Шрифт не найден. Используется стандартный.")
            font = ImageFont.load_default()

        # Настройки позиции
        x, y = 50, 50  # Координаты
        fill_color = (255, 255, 255)

        draw.text((x, y), f"K: {k_value}", font=font, fill=fill_color)

        bg.save(result_path)
        print(f"? Изображение сохранено: {result_path}")

    except Exception as e:
        print(f"? Ошибка отрисовки: {e}")

def draw_kda_text(image, kda_value, position=(100, 100),
                  font_path="arial.ttf", font_size=30,
                  fill=(255, 255, 255)):
    try:
        draw = ImageDraw.Draw(image)

        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            print("⚠️ Шрифт не найден, используется стандартный.")
            font = ImageFont.load_default()

        # Рисуем текст
        draw.text(position, kda_value, font=font, fill=fill)

    except Exception as e:
        print(f"❌ Ошибка при отрисовке K/D/A текста: {e}")

def draw_online_status_icon(base_image, status, position=(0, 0),
                            icon_online_path="online.png",
                            icon_offline_path="offline.png",
                            icon_unknown_path="unknown.png",
                            icon_size=(40, 15)):
    """
    Рисует иконку статуса (онлайн/оффлайн/неизвестно) поверх base_image.
    """
    try:
        if status.lower() == "online":
            icon = Image.open(icon_online_path).convert("RGBA")
        elif status.lower() == "offline":
            icon = Image.open(icon_offline_path).convert("RGBA")
        else:
            icon = Image.open(icon_unknown_path).convert("RGBA")

        icon = icon.resize(icon_size)

        base_image.paste(icon, position, icon)
    except Exception as e:
        print(f"Ошибка при вставке иконки статуса: {e}")



def draw_max_streak_text(base_image, streak_value, position=(160, 394), font_path="arial.ttf",
                         font_size=14, fill=(255, 255, 255, 255)):
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(base_image)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    # Выводим только число, без надписи
    draw.text(position, str(streak_value), font=font, fill=fill)


def draw_current_streak_text(base_image, streak_value, position=(145, 390), font_path="arial.ttf",
                             font_size=15, fill=(255, 255, 255, 255)):
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(base_image)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    draw.text(position, str(streak_value), font=font, fill=fill)


# функция для создания прогресс бара
def create_progress(percent):
    size = 250
    image = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    center = size // 2

    # Внешний круг (фон)
    draw.arc((20, 20, size - 20, size - 20), start=0, end=360, fill=(60, 60, 60), width=20)

    # Внутренний круг (тень для эффекта глубины)
    draw.arc((22, 22, size - 22, size - 22), start=-90, end=-90 + percent * 3.6, fill=(0, 120, 0), width=16)

    # Основной прогресс-бар - зеленый градиент
    if percent > 0:
        # Яркий зеленый для основного прогресса
        draw.arc((20, 20, size - 20, size - 20), start=-90, end=-90 + percent * 3.6, fill=(34, 197, 94), width=20)

        # Светлый зеленый поверх для эффекта свечения
        draw.arc((18, 18, size - 18, size - 18), start=-90, end=-90 + percent * 3.6, fill=(74, 222, 128), width=6)

    # Добавляем внутренний круг для лучшего контраста
    inner_circle_radius = 80
    draw.ellipse(
        (center - inner_circle_radius, center - inner_circle_radius,
         center + inner_circle_radius, center + inner_circle_radius),
        fill=(40, 40, 40, 200)
    )

    # Добавляем тень для текста
    try:
        font = ImageFont.truetype("arial.ttf", 32)
        shadow_font = ImageFont.truetype("arial.ttf", 32)
    except:
        font = ImageFont.load_default()
        shadow_font = ImageFont.load_default()

    text = f"{int(percent)}%"

    # Используем textbbox вместо textsize для новых версий Pillow
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        # Fallback для старых версий Pillow
        text_width, text_height = draw.textsize(text, font)

    text_x = center - text_width // 2
    text_y = center - text_height // 2

    # Рисуем тень текста (темно-серая)
    draw.text((text_x + 2, text_y + 2), text, font=shadow_font, fill=(20, 20, 20, 180))

    # Рисуем основной текст (белый)
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))

    # Добавляем блик для эффекта стекла
    if percent > 10:  # Показываем блик только если есть прогресс
        highlight_end = min(-90 + percent * 3.6, -45)  # Ограничиваем блик
        draw.arc((25, 25, size - 25, size - 25), start=-90, end=highlight_end,
                 fill=(255, 255, 255, 100), width=4)

    return image


# Функция для скачивания флага с кэшированием
async def download_flag_async(url: str, filename="parsed-flag.png"):
    if not url:
        return None

    try:
        # Проверяем кэш
        cached_data = image_cache.get(url)
        if cached_data:
            print(f"?? Флаг загружен из кэша: {url}")
            async with aiofiles.open(filename, mode='wb') as f:
                await f.write(cached_data)
            return filename

        # Скачиваем если не в кэше
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.read()

                    # Сохраняем в кэш
                    image_cache.put(url, data)
                    print(f"?? Флаг скачан и сохранен в кэш: {url}")

                    # Сохраняем в файл
                    async with aiofiles.open(filename, mode='wb') as f:
                        await f.write(data)
                    return filename
                else:
                    return None
    except Exception as e:
        print(f"Error downloading flag: {e}")
        return None


# Асинхронная функция для загрузки изображения героя с кэшированием
async def download_hero_image_async(url: str):
    if not url:
        return None

    try:
        # Проверяем кэш
        cached_data = image_cache.get(url)
        if cached_data:
            print(f"?? Изображение героя загружено из кэша: {url}")
            return cached_data

        # Скачиваем если не в кэше
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.read()

                    # Сохраняем в кэш
                    image_cache.put(url, data)
                    print(f"?? Изображение героя скачано и сохранено в кэш: {url}")

                    return data
                else:
                    return None
    except Exception as e:
        print(f"Error downloading hero image: {e}")
        return None


# Асинхронная функция для парсинга игр
async def parse_game_data_async(nickname: str):
    url = f"https://iccup.com/ru/dota/gamingprofile/{nickname}.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": url
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    print(f"Ошибка загрузки страницы: {response.status}")
                    return {}

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                print(f"Парсим данные для {nickname}")
                
                # Словарь для хранения данных
                game_data = {}
                
                # Проверяем наличие таблицы
                result_table = soup.select('#result-table')
                if not result_table:
                    print("Таблица #result-table не найдена")
                else:
                    print(f"Найдена таблица результатов")

                # Парсим таблицу последних игр
                rows = soup.select('#result-table tr')

                for idx, row in enumerate(rows[:5], start=1):  # Берем только первые 5 игр
                    try:
                        hero_img = row.select_one('td img')
                        if hero_img:
                            hero_img_src = hero_img.get('src', '')
                            if hero_img_src.startswith('/'):
                                hero_img_src = "https://iccup.com" + hero_img_src
                        else:
                            hero_img_src = ""

                        hero_name_elem = row.select_one('td span')
                        hero_name = hero_name_elem.text.strip() if hero_name_elem else "Unknown"

                        cells = row.select('td')
                        if len(cells) >= 5:
                            mode = cells[1].get_text(strip=True)
                            time = cells[2].text.strip()

                            # Парсим KDA
                            kda_td = cells[3]
                            k_elem = kda_td.select_one('.c-red')
                            d_elem = kda_td.select_one('.c-blue')
                            a_elem = kda_td.select_one('.c-green')

                            k = k_elem.text if k_elem else "0"
                            d = d_elem.text if d_elem else "0"
                            a = a_elem.text if a_elem else "0"

                            # Парсим очки
                            points_td = cells[4]
                            result = "win" if points_td.select_one(".l-win") else "lose"
                            points_elem = points_td.select_one('span.darkgreen, span.darkred')
                            points = points_elem.text.strip() if points_elem else "0"

                            game_data[f'hero{idx}'] = hero_name
                            game_data[f'hero_img{idx}'] = hero_img_src
                            game_data[f'mode{idx}'] = mode
                            game_data[f'time{idx}'] = time
                            game_data[f'kills{idx}'] = k
                            game_data[f'deaths{idx}'] = d
                            game_data[f'assists{idx}'] = a
                            game_data[f'points{idx}'] = points
                            game_data[f'result{idx}'] = result

                    except Exception as e:
                        print(f"Ошибка при парсинге игры {idx}: {e}")
                        continue

                # Найдём все блоки top-hero
                top_hero_blocks = soup.find_all("div", class_="top-hero")

                for block in top_hero_blocks:
                    header = block.find_previous("h4")
                    if header and "Лучший герой" in header.text:
                        try:
                            hero_img_elem = block.find("img")
                            hero_name_elem = block.find("span")
                            hero_kda_elem = block.find("b")

                            if hero_img_elem and hero_name_elem and hero_kda_elem:
                                hero_img = hero_img_elem.get("src", "")
                                if hero_img.startswith('/'):
                                    hero_img = "https://iccup.com" + hero_img

                                game_data["top_hero_name"] = hero_name_elem.text.strip()
                                game_data["top_hero_img"] = hero_img
                                game_data["top_hero_kda"] = hero_kda_elem.text.strip()
                            else:
                                print("Не найдены все элементы лучшего героя.")
                        except Exception as e:
                            print(f"Ошибка при парсинге лучшего героя: {e}")
                        break
                else:
                    game_data["top_hero_name"] = "Unknown"
                    game_data["top_hero_img"] = None
                    game_data["top_hero_kda"] = "-"

                # Парсим "Лучший по убийствам"
                for block in top_hero_blocks:
                    header = block.find_previous("h4")
                    if header and "убийств" in header.text:
                        try:
                            killer_img_elem = block.find("img")
                            killer_name_elem = block.find("span")
                            killer_avg_elem = block.find("b")

                            if killer_img_elem and killer_name_elem and killer_avg_elem:
                                killer_img = killer_img_elem.get("src", "")
                                if killer_img.startswith('/'):
                                    killer_img = "https://iccup.com" + killer_img

                                game_data["killer_hero_name"] = killer_name_elem.text.strip()
                                game_data["killer_hero_img"] = killer_img
                                game_data["killer_avg_kills"] = killer_avg_elem.text.strip()
                        except Exception as e:
                            print(f"Ошибка при парсинге лучшего убийцы: {e}")
                        break

                return game_data

    except Exception as e:
        print(f"Ошибка при парсинге данных игр: {e}")
        return {}


def add_rating_image(base_image, rating_value):
    if rating_value >= 30000:
        rating_image_path = "rating/rating_30k_plus.jpg"
    elif 25000 <= rating_value <= 29999:
        rating_image_path = "rating/rating_S_plus.png"
    elif 20000 <= rating_value <= 24999:
        rating_image_path = "rating/rating_S.png"
    elif 15000 <= rating_value <= 19999:
        rating_image_path = "rating/rating_A_minus.jpg"
    elif 12000 <= rating_value <= 14999:
        rating_image_path = "rating/rating_A_plus.jpg"
    elif 10500 <= rating_value <= 11999:
        rating_image_path = "rating/rating_A.jpg"
    elif 9000 <= rating_value <= 10499:
        rating_image_path = "rating/rating_A_minus.jpg"
    elif 8000 <= rating_value <= 8999:
        rating_image_path = "rating/rating_B_plus.jpg"
    elif 7000 <= rating_value <= 7999:
        rating_image_path = "rating/rating_B.jpg"
    elif 6000 <= rating_value <= 6999:
        rating_image_path = "rating/rating_B_minus.jpg"
    elif 5000 <= rating_value <= 5999:
        rating_image_path = "rating/rating_C_plus.jpg"
    elif 4000 <= rating_value <= 4999:
        rating_image_path = "rating/rating_C.jpg"
    elif 3000 <= rating_value <= 3999:
        rating_image_path = "rating/rating_C_minus.jpg"
    elif 2000 <= rating_value <= 2999:
        rating_image_path = "rating/rating_D_plus.jpg"
    elif 900 <= rating_value <= 1999:
        rating_image_path = "rating/rating_D.jpg"
    elif 400 <= rating_value <= 899:
        rating_image_path = "rating/rating_D_minus.jpg"
    else:
        rating_image_path = "rating/rating_default.png"  # Для значений ниже 400

    try:
        # Открываем изображение рейтинга
        rating_image = Image.open(rating_image_path)
        # Изменяем размер рейтинга (ширина 75, высота 33)
        rating_image = rating_image.resize((75, 33))
        # Координаты, куда вставлять изображение (x, y)
        position = (35, 120)
        # Вставляем изображение рейтинга на base_image
        base_image.paste(rating_image, position, rating_image if rating_image.mode == 'RGBA' else None)
    except Exception as e:
        print(f"Ошибка при добавлении изображения рейтинга: {e}")


# Функция для отрисовки K-value поверх изображения
def draw_k_value_on_image(base_image, k_value, position=(50, 80), font_path="arial.ttf", font_size=36,
                          fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0)):
    """
    Рисует значение K поверх изображения
    """
    draw = ImageDraw.Draw(base_image)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    draw.text(position, f"K: {k_value}", font=font, fill=fill)


# Функция для отрисовки рейтинга текстом
def draw_rating_text(base_image, rating_str, position=(130, 122), font_path="arial.ttf", font_size=34,
                     fill=(255, 255, 255, 255)):
    draw = ImageDraw.Draw(base_image)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()
    draw.text(position, rating_str, font=font, fill=fill)


#Функция для отрисовки Побед/Поражений/Ливов
def draw_win_lose_leave_text(base_image, wll_str, position=(130, 220), font_path="arial.ttf", font_size=26,
                             fill=(150, 255, 150, 255)):
    """
    Функция для отрисовки статистики Победы/Поражения/Ливы на изображении
    """
    draw = ImageDraw.Draw(base_image)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    # Форматируем текст для отображения (только цифры)
    display_text = f"{wll_str}"
    draw.text(position, display_text, font=font, fill=fill)




# Функция для экспорта команды stats
def setup_stats_command(client):
    @client.tree.command(name="stats", description="Показать статистику игрока ICCup")
    @app_commands.describe(nickname="Ник игрока ICCup")
    async def stats(interaction: discord.Interaction, nickname: str):
        await interaction.response.defer()
        try:
            # Получаем основные данные профиля
            data = fetch_iccup_stats(nickname)
            k_value = data.get("Крутость", "—")
            if not data or 'Ошибка' in data:
                await interaction.followup.send(f"? Игрок `{nickname}` не найден или произошла ошибка.")
                return

            # Получаем данные об играх асинхронно
            game_data = await parse_game_data_async(nickname)

            # Скачиваем флаг
            flag_url = data.get('Флаг')
            flag_path = await download_flag_async(flag_url)

            result_path = "result.png"
            background_path = "ui.png"

            background = Image.open(background_path).convert("RGBA")
            
            # Добавляем элитную иконку если есть
            if data.get("Элитный"):
                try:
                    elite_icon = Image.open("elite.png").convert("RGBA")
                    elite_icon = elite_icon.resize((60, 40))
                    background.paste(elite_icon, (377, 12), elite_icon)
                except Exception as e:
                    print(f"Ошибка при вставке элитной иконки: {e}")

            # Добавляем флаг
            if flag_path:
                try:
                    flag_img = Image.open(flag_path).convert("RGBA")
                    flag_img = flag_img.resize((70, 50))
                    background.paste(flag_img, (25, 37), flag_img)
                except Exception as e:
                    print(f"Ошибка при вставке флага: {e}")

            draw = ImageDraw.Draw(background)
            font_path = "arial.ttf"
            font_size = 35
            try:
                font = ImageFont.truetype(font_path, font_size)
                font_small = ImageFont.truetype(font_path, 20)
                font_medium = ImageFont.truetype(font_path, 22)
            except:
                font = ImageFont.load_default()
                font_small = ImageFont.load_default()
                font_medium = ImageFont.load_default()

            # Рисуем никнейм
            font = ImageFont.truetype("arial.ttf", 40)
            draw.text((107, 40), nickname, font=font, fill=(255, 255, 255))

            # Получение и обработка рейтинга
            rating_value = data.get("Рейтинг", 0)
            try:
                rating_value = int(str(rating_value).replace(' ', '').replace(',', '').replace('.', ''))
            except:
                rating_value = 0

            # Вставляем картинку рейтинга
            add_rating_image(background, rating_value)

            # Добавляем рейтинг текстом
            draw_rating_text(
                background,
                str(data.get("Рейтинг", "")),
                position=(133, 122),
                font_path="arial.ttf",
                font_size=34,
                fill=(255, 255, 255, 255)
            )

            online_status = data.get("Онлайн", "Unknown")
            draw_online_status_icon(
                background,
                online_status,
                position=(178, 446),
                icon_size=(69, 25),
                icon_online_path="online.png",
                icon_offline_path="offline.png",
                icon_unknown_path="unknown.jpg"
            )

            draw_k_value_on_image(
                background, 
                k_value,
                position=(42, 167),
                font_path="arial.ttf",
                font_size=25,
                fill=(255, 235, 130),
                stroke_width=3,
                stroke_fill=(0, 0, 0)
            )

            draw_kda_text(
                background,
                kda_value=str(data.get("K/D/A", "0/0/0")),
                position=(130, 169),
                font_path="arial.ttf",
                font_size=25,
                fill=(255, 255, 255, 255)
            )

            draw_kda_text(
                background,
                kda_value=str(data.get("K/D/A", "0/0/0")),
                position=(180, 332),
                font_path="arial.ttf",
                font_size=13,
                fill=(255, 255, 255)
            )

            # Рейтинг в другом месте
            draw_rating_text(
                background,
                str(data.get("Рейтинг", "")),
                position=(187, 300),
                font_path="arial.ttf",
                font_size=14,
                fill=(255, 255, 255, 255)
            )

            # Максимальный стрик
            max_streak_value = data.get("Макс. стрик побед", "—")
            draw_max_streak_text(
                background,
                max_streak_value,
                position=(200, 390),
                font_path="arial.ttf",
                font_size=14,
                fill=(255, 255, 255, 255)
            )

            # Текущий стрик
            current_streak_value = data.get("Текущий стрик", "—")
            draw_current_streak_text(
                background,
                current_streak_value,
                position=(200, 423),
                font_path="arial.ttf",
                font_size=14,
                fill=(255, 255, 255, 255)
            )

            # Победы/Поражения/Ливы
            win_lose_leave_value = data.get("Победы / Поражения / Ливы", "—")
            draw_win_lose_leave_text(
                background,
                win_lose_leave_value,
                position=(182, 361),
                font_path="arial.ttf",
                font_size=14,
                fill=(255, 255, 255, 255)
            )

            # Отрисовка лучшего героя
            if game_data.get("top_hero_kda"):
                draw.text((344, 273), f": {game_data['top_hero_kda']}", font=font_medium, fill=(255, 255, 255))

                # Загружаем иконку лучшего героя
                if game_data.get("top_hero_img"):
                    hero_img_data = await download_hero_image_async(game_data["top_hero_img"])
                    if hero_img_data:
                        try:
                            hero_icon = Image.open(BytesIO(hero_img_data)).convert("RGBA")
                            hero_icon = hero_icon.resize((50, 45))
                            background.paste(hero_icon, (291, 259), hero_icon)
                        except Exception as e:
                            print(f"Ошибка загрузки иконки лучшего героя: {e}")

            # Отрисовка лучшего по убийствам
            if game_data.get("killer_avg_kills"):
                draw.text((357, 418), f"{game_data['killer_avg_kills']}", font=font_medium, fill=(255, 255, 255))

                # Загружаем иконку убийцы
                if game_data.get("killer_hero_img"):
                    killer_img_data = await download_hero_image_async(game_data["killer_hero_img"])
                    if killer_img_data:
                        try:
                            killer_icon = Image.open(BytesIO(killer_img_data)).convert("RGBA")
                            killer_icon = killer_icon.resize((50, 45))
                            background.paste(killer_icon, (293, 403), killer_icon)
                        except Exception as e:
                            print(f"Ошибка загрузки иконки убийцы: {e}")

            # Координаты для последних игр
            icon_y_offsets = {
                1: 552,
                2: 596,
                3: 640,
                4: 683,
                5: 727,
            }

            text_x_base = 70
            icon_height = 30
            text_y_correction = (icon_height - 20) // 2

            # Отрисовка последних игр
            for i in range(1, 6):
                if game_data.get(f'mode{i}'):
                    y = icon_y_offsets[i] + text_y_correction
                    draw.text((text_x_base, y), f"{game_data.get(f'mode{i}', '-')}", font=font_small, fill=(100, 200, 255))
                    draw.text((text_x_base + 80, y), f"{game_data.get(f'time{i}', '-')}", font=font_small,
                            fill=(70, 180, 255))

                    # Получаем значения K/D/A
                    kills = str(game_data.get(f'kills{i}', '-'))
                    deaths = str(game_data.get(f'deaths{i}', '-'))
                    assists = str(game_data.get(f'assists{i}', '-'))

                    # Начальная позиция X
                    x = text_x_base + 160

                    # Рисуем kills (зелёный)
                    draw.text((x, y), kills, font=font_small, fill=(0, 255, 0))
                    x += font_small.getlength(kills + "/")

                    # Рисуем deaths (красный)
                    draw.text((x, y), deaths, font=font_small, fill=(255, 0, 0))
                    x += font_small.getlength(deaths + "/")

                    # Рисуем assists (синий)
                    draw.text((x, y), assists, font=font_small, fill=(0, 128, 255))
                    points_str = game_data.get(f"points{i}", "-")
                    color = (255, 0, 0) if points_str.startswith("-") else (0, 255, 0)

                    draw.text((text_x_base + 260, y), points_str, font=font_small, fill=color)

                    # Загружаем иконку героя
                    hero_img_url = game_data.get(f'hero_img{i}')
                    if hero_img_url:
                        hero_img_data = await download_hero_image_async(hero_img_url)
                        if hero_img_data:
                            try:
                                hero_icon = Image.open(BytesIO(hero_img_data)).convert("RGBA")
                                hero_icon = hero_icon.resize((30, 30))
                                background.paste(hero_icon, (30, icon_y_offsets[i]), hero_icon)
                            except Exception as e:
                                print(f"Ошибка загрузки иконки героя {i}: {e}")

            # Отрисовка прогресс-бара винрейта
            winrate_percent_str = data.get("Победы %", "0")
            try:
                progress_percent = float(winrate_percent_str.replace('%', '').strip())
            except ValueError:
                progress_percent = 0
            
            progress_img = create_progress(progress_percent)
            progress_img = progress_img.resize((150, 150))
            background.paste(progress_img, (283, 64), progress_img)

            # Сохраняем итоговое изображение
            background.save(result_path)
            await interaction.followup.send(file=discord.File(result_path))

        except Exception as e:
            await interaction.followup.send("? Ошибка при создании изображения.")
            print(f"Ошибка в команде stats: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Очистка временных файлов
            if os.path.exists(result_path):
                os.remove(result_path)
            if flag_path and os.path.exists(flag_path):
                os.remove(flag_path)
def setup_stats_command(client):
    @client.tree.command(name="stats", description="Показать статистику игрока ICCup")
    @app_commands.describe(nickname="Ник игрока ICCup")
    async def stats(interaction: discord.Interaction, nickname: str):
        await interaction.response.defer()
        try:
            # Получаем основные данные профиля
            data = fetch_iccup_stats(nickname)
            k_value = data.get("Крутость", "—")
            if not data or 'Ошибка' in data:
                await interaction.followup.send(f"? Игрок `{nickname}` не найден или произошла ошибка.")
                return

            # Получаем данные об играх асинхронно
            game_data = await parse_game_data_async(nickname)

            # Скачиваем флаг
            flag_url = data.get('Флаг')
            flag_path = await download_flag_async(flag_url)

            result_path = "result.png"
            background_path = "ui.png"

            background = Image.open(background_path).convert("RGBA")
            
            # [Остальной код функции stats остаётся тем же]
            # Добавляем элитную иконку если есть
            if data.get("Элитный"):
                try:
                    elite_icon = Image.open("elite.png").convert("RGBA")
                    elite_icon = elite_icon.resize((60, 40))
                    background.paste(elite_icon, (377, 12), elite_icon)
                except Exception as e:
                    print(f"Ошибка при вставке элитной иконки: {e}")

            # Добавляем флаг
            if flag_path:
                try:
                    flag_img = Image.open(flag_path).convert("RGBA")
                    flag_img = flag_img.resize((70, 50))
                    background.paste(flag_img, (25, 37), flag_img)
                except Exception as e:
                    print(f"Ошибка при вставке флага: {e}")

            draw = ImageDraw.Draw(background)
            font_path = "arial.ttf"
            font_size = 35
            try:
                font = ImageFont.truetype(font_path, font_size)
                font_small = ImageFont.truetype(font_path, 20)
                font_medium = ImageFont.truetype(font_path, 22)
            except:
                font = ImageFont.load_default()
                font_small = ImageFont.load_default()
                font_medium = ImageFont.load_default()

            # Рисуем никнейм
            font = ImageFont.truetype("arial.ttf", 40)
            draw.text((107, 40), nickname, font=font, fill=(255, 255, 255))

            # Получение и обработка рейтинга
            rating_value = data.get("Рейтинг", 0)
            try:
                rating_value = int(str(rating_value).replace(' ', '').replace(',', '').replace('.', ''))
            except:
                rating_value = 0

            # Вставляем картинку рейтинга
            add_rating_image(background, rating_value)

            # Добавляем рейтинг текстом
            draw_rating_text(
                background,
                str(data.get("Рейтинг", "")),
                position=(133, 122),
                font_path="arial.ttf",
                font_size=34,
                fill=(255, 255, 255, 255)
            )

            online_status = data.get("Онлайн", "Unknown")
            draw_online_status_icon(
                background,
                online_status,
                position=(178, 446),
                icon_size=(69, 25),
                icon_online_path="online.png",
                icon_offline_path="offline.png",
                icon_unknown_path="unknown.jpg"
            )

            draw_k_value_on_image(
                background, 
                k_value,
                position=(42, 167),
                font_path="arial.ttf",
                font_size=25,
                fill=(255, 235, 130),
                stroke_width=3,
                stroke_fill=(0, 0, 0)
            )

            draw_kda_text(
                background,
                kda_value=str(data.get("K/D/A", "0/0/0")),
                position=(130, 169),
                font_path="arial.ttf",
                font_size=25,
                fill=(255, 255, 255, 255)
            )

            draw_kda_text(
                background,
                kda_value=str(data.get("K/D/A", "0/0/0")),
                position=(180, 332),
                font_path="arial.ttf",
                font_size=13,
                fill=(255, 255, 255)
            )

            # Рейтинг в другом месте
            draw_rating_text(
                background,
                str(data.get("Рейтинг", "")),
                position=(187, 300),
                font_path="arial.ttf",
                font_size=14,
                fill=(255, 255, 255, 255)
            )

            # Максимальный стрик
            max_streak_value = data.get("Макс. стрик побед", "—")
            draw_max_streak_text(
                background,
                max_streak_value,
                position=(200, 390),
                font_path="arial.ttf",
                font_size=14,
                fill=(255, 255, 255, 255)
            )

            # Текущий стрик
            current_streak_value = data.get("Текущий стрик", "—")
            draw_current_streak_text(
                background,
                current_streak_value,
                position=(200, 423),
                font_path="arial.ttf",
                font_size=14,
                fill=(255, 255, 255, 255)
            )

            # Победы/Поражения/Ливы
            win_lose_leave_value = data.get("Победы / Поражения / Ливы", "—")
            draw_win_lose_leave_text(
                background,
                win_lose_leave_value,
                position=(182, 361),
                font_path="arial.ttf",
                font_size=14,
                fill=(255, 255, 255, 255)
            )

            # Отрисовка прогресс-бара винрейта
            winrate_percent_str = data.get("Победы %", "0")
            try:
                progress_percent = float(winrate_percent_str.replace('%', '').strip())
            except ValueError:
                progress_percent = 0
            
            progress_img = create_progress(progress_percent)
            progress_img = progress_img.resize((150, 150))
            background.paste(progress_img, (283, 64), progress_img)

            # Отрисовка лучшего героя
            if game_data.get("top_hero_kda"):
                draw.text((344, 273), f": {game_data['top_hero_kda']}", font=font_medium, fill=(255, 255, 255))

                # Загружаем иконку лучшего героя
                if game_data.get("top_hero_img"):
                    hero_img_data = await download_hero_image_async(game_data["top_hero_img"])
                    if hero_img_data:
                        try:
                            hero_icon = Image.open(BytesIO(hero_img_data)).convert("RGBA")
                            hero_icon = hero_icon.resize((50, 45))
                            background.paste(hero_icon, (291, 259), hero_icon)
                        except Exception as e:
                            print(f"Ошибка загрузки иконки лучшего героя: {e}")

            # Отрисовка лучшего по убийствам
            if game_data.get("killer_avg_kills"):
                draw.text((357, 418), f"{game_data['killer_avg_kills']}", font=font_medium, fill=(255, 255, 255))

                # Загружаем иконку убийцы
                if game_data.get("killer_hero_img"):
                    killer_img_data = await download_hero_image_async(game_data["killer_hero_img"])
                    if killer_img_data:
                        try:
                            killer_icon = Image.open(BytesIO(killer_img_data)).convert("RGBA")
                            killer_icon = killer_icon.resize((50, 45))
                            background.paste(killer_icon, (293, 403), killer_icon)
                        except Exception as e:
                            print(f"Ошибка загрузки иконки убийцы: {e}")

            # Координаты для последних игр
            icon_y_offsets = {
                1: 552,
                2: 596,
                3: 640,
                4: 683,
                5: 727,
            }

            text_x_base = 70
            icon_height = 30
            text_y_correction = (icon_height - 20) // 2

            # Отрисовка последних игр
            for i in range(1, 6):
                if game_data.get(f'mode{i}'):
                    y = icon_y_offsets[i] + text_y_correction
                    draw.text((text_x_base, y), f"{game_data.get(f'mode{i}', '-')}", font=font_small, fill=(100, 200, 255))
                    draw.text((text_x_base + 80, y), f"{game_data.get(f'time{i}', '-')}", font=font_small, 
                            fill=(70, 180, 255))

                    # Получаем значения K/D/A
                    kills = str(game_data.get(f'kills{i}', '-'))
                    deaths = str(game_data.get(f'deaths{i}', '-'))
                    assists = str(game_data.get(f'assists{i}', '-'))

                    # Начальная позиция X
                    x = text_x_base + 160

                    # Рисуем kills (зелёный)
                    draw.text((x, y), kills, font=font_small, fill=(0, 255, 0))
                    x += font_small.getlength(kills + "/")  # учёт ширины kills и слеша

                    # Рисуем deaths (красный)
                    draw.text((x, y), deaths, font=font_small, fill=(255, 0, 0))
                    x += font_small.getlength(deaths + "/")  # учёт ширины deaths и слеша

                    # Рисуем assists (синий)
                    draw.text((x, y), assists, font=font_small, fill=(0, 128, 255))
                    points_str = game_data.get(f"points{i}", "-")
                    color = (255, 0, 0) if points_str.startswith("-") else (0, 255, 0)

                    draw.text((text_x_base + 260, y), points_str, font=font_small, fill=color)

                    # Загружаем иконку героя
                    hero_img_url = game_data.get(f'hero_img{i}')
                    if hero_img_url:
                        hero_img_data = await download_hero_image_async(hero_img_url)
                        if hero_img_data:
                            try:
                                hero_icon = Image.open(BytesIO(hero_img_data)).convert("RGBA")
                                hero_icon = hero_icon.resize((30, 30))
                                background.paste(hero_icon, (30, icon_y_offsets[i]), hero_icon)
                            except Exception as e:
                                print(f"Ошибка загрузки иконки героя {i}: {e}")

            # Сохраняем итоговое изображение
            background.save(result_path)
            await interaction.followup.send(file=discord.File(result_path))

        except Exception as e:
            await interaction.followup.send("? Ошибка при создании изображения.")
            print(f"Ошибка в команде stats: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Очистка временных файлов
            if os.path.exists(result_path):
                os.remove(result_path)
            if flag_path and os.path.exists(flag_path):
                os.remove(flag_path)

# --- Запуск ---
