import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

BASE_URL = "https://iccup.com/ru/dota/gamingprofile/"
PROFILE_BASE_URL = "https://iccup.com/profile/view/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def get_soup(url):
    """
    Отправляет GET-запрос по URL и возвращает объект BeautifulSoup.
    """
    try:
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
        return BeautifulSoup(res.text, "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе {url}: {e}")
        return None
    except Exception as e:
        print(f"Неизвестная ошибка при получении супа для {url}: {e}")
        return None


def parse_kda(soup):
    """
    Парсит K/D/A из HTML супа, используя улучшенный метод.
    """
    kda_block = soup.find("div", class_="i-kda left")

    if not kda_block:
        return "0/0/0"

    # Извлекаем только цифры (K, D, A)
    numbers = kda_block.find_all("span", class_=["c-green", "c-red", "c-blue"])
    if not numbers or len(numbers) < 3:
        return "0/0/0"

    kda = "/".join(num.text.strip() for num in numbers)
    print(kda_block)
    print(kda)
    return kda


async def parse_game_data_async(nickname):
    """
    Асинхронно получает и парсит данные об играх игрока
    """
    try:
        url = f"{BASE_URL}{nickname}"
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        game_data = {}

        # Получаем данные о лучшем герое и его KDA
        top_hero_div = soup.find("div", class_="best-hero")
        if top_hero_div:
            hero_img = top_hero_div.find("img")
            if hero_img and hero_img.get("src"):
                game_data["top_hero_img"] = hero_img["src"]
            
            kda_span = top_hero_div.find("span", class_="kda")
            if kda_span:
                game_data["top_hero_kda"] = kda_span.text.strip()

        # Получаем данные о лучшем убийце
        killer_div = soup.find("div", class_="killer-hero")
        if killer_div:
            hero_img = killer_div.find("img")
            if hero_img and hero_img.get("src"):
                game_data["killer_hero_img"] = hero_img["src"]
            
            kills_span = killer_div.find("span", class_="kills")
            if kills_span:
                game_data["killer_avg_kills"] = kills_span.text.strip()

        # Парсим последние игры
        games_table = soup.find("table", class_="last-games")
        if games_table:
            for i, row in enumerate(games_table.find_all("tr")[:5], 1):
                cells = row.find_all("td")
                if len(cells) >= 6:
                    # Режим и время
                    game_data[f"mode{i}"] = cells[1].text.strip()
                    game_data[f"time{i}"] = cells[2].text.strip()
                    
                    # KDA
                    kda = cells[3].text.strip().split("/")
                    if len(kda) == 3:
                        game_data[f"kills{i}"] = kda[0]
                        game_data[f"deaths{i}"] = kda[1]
                        game_data[f"assists{i}"] = kda[2]
                    
                    # Очки
                    game_data[f"points{i}"] = cells[4].text.strip()
                    
                    # Иконка героя
                    hero_img = cells[0].find("img")
                    if hero_img and hero_img.get("src"):
                        game_data[f"hero_img{i}"] = hero_img["src"]

        return game_data
    except Exception as e:
        print(f"Ошибка при парсинге данных игр для {nickname}: {e}")
        return {}

def parse_online_status(html):
    soup = BeautifulSoup(html, "html.parser")
    with open("real_response.html", "w", encoding="utf-8") as f:
        f.write(html)
    # Найти div с классом bnet-status
    status_div = soup.find("div", class_="bnet-status")

    if not status_div:
        print("❌ Статус не найден в HTML")
        return "unknown"

    # Получить список классов
    classes = status_div.get("class", [])

    print("✅ Классы статуса:", classes)

    if "online" in classes:
        return "online"
    elif "offline" in classes:
        return "offline"

    return "unknown"

def download_flag(flag_url: str, save_path="parsed-flag.png"):
    """
    Скачивает изображение флага и сохраняет его по указанному пути.
    """
    try:
        response = requests.get(flag_url, stream=True)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        img.save(save_path)
        return save_path
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при скачивании флага {flag_url}: {e}")
        return None
    except Exception as e:
        print(f"Неизвестная ошибка при обработке флага: {e}")
        return None


def fetch_iccup_stats(nickname):
    """
    Собирает статистику игрока с iCCup по заданному никнейму.
    """
    try:
        dota_url = f"{BASE_URL}{nickname}.html"
        profile_url = f"{PROFILE_BASE_URL}{nickname}.html"

        soup_dota = get_soup(dota_url)
        soup_profile = get_soup(profile_url)

        if not soup_dota:
            return {"Ошибка": f"Не удалось получить данные со страницы Dota: {dota_url}"}
        if not soup_profile:
            return {"Ошибка": f"Не удалось получить данные со страницы профиля: {profile_url}"}

        stats = {"Имя": nickname}

        # Парсинг основной статистики Dota
        stats["Рейтинг"] = soup_dota.select_one("span.i-pts").text.strip() if soup_dota.select_one(
            "span.i-pts") else "—"

        main_stata_tds = soup_dota.select("div.main-stata-5x5 td")
        stats["Положение в рейтинге"] = main_stata_tds[1].text.strip() if len(main_stata_tds) > 1 else "—"

        # Крутость (безопасный парсинг)
        k_value = "0"
        k_num_tag = soup_dota.select_one("span#k-num")

        if k_num_tag:
            k_raw = k_num_tag.text.strip()
            k_raw = k_raw.replace("K", "").replace("k", "").strip()
            k_value = ''.join(c for c in k_raw if c.isdigit() or c == '.')
            if not k_value:
                k_value = "0"

        stats["Крутость"] = k_value

        # KDA (Используем новую функцию parse_kda)
        stats["K/D/A"] = parse_kda(soup_dota)

        # Таблица статистики
        def get_stat_value(soup, label):
            td_label = soup.find("td", string=label)
            return td_label.find_next_sibling("td").text.strip() if td_label and td_label.find_next_sibling(
                "td") else "—"

        stats["Победы / Поражения / Ливы"] = get_stat_value(soup_dota, "Win/Lose/Leave")
        stats["Курьеров убито"] = get_stat_value(soup_dota, "Курьеров убито")
        stats["Нейтралов убито"] = get_stat_value(soup_dota, "Нейтралов убито")
        stats["Налетанные часы"] = get_stat_value(soup_dota, "Налетанные часы")
        stats["Победы %"] = get_stat_value(soup_dota, "Победы")
        stats["Кол-во ливов"] = get_stat_value(soup_dota, "Кол-во ливов")

        лучший_счет_td = soup_dota.find("td", string="Лучший счет")
        stats["Лучший счет"] = лучший_счет_td.find_next_sibling("td").get_text(
            separator=" ").strip() if лучший_счет_td and лучший_счет_td.find_next_sibling("td") else "—"

        stats["Макс. стрик побед"] = get_stat_value(soup_dota, "Макс. стрик побед")
        stats["Текущий стрик"] = get_stat_value(soup_dota, "Текущий стрик")

        status_html = str(soup_dota)
        stats["Онлайн"] = parse_online_status(status_html)

        # Парсинг KDA из блока с 3 значениями (bidlokod1)
        kda_table_container = soup_dota.find("div", class_="kda-table")
        if kda_table_container:
            kda_spans = kda_table_container.find_all("span", class_="bidlokod1")
            stats["KDA из таблицы"] = [span.get_text(strip=True) for span in kda_spans[:3]] if kda_spans else ["—", "—",
                                                                                                               "—"]
        else:
            stats["KDA из таблицы"] = ["—", "—", "—"]

        # Герои (лучшие)
        best_hero_section = soup_dota.select("div.top-hero")
        for section in best_hero_section:
            title_tag = section.find("h4")
            hero_tag = section.find("span")
            value_tag = section.find("p")
            if title_tag and hero_tag and value_tag:
                title = title_tag.text.strip()
                hero = hero_tag.text.strip()
                value = value_tag.text.strip()
                stats[f"Лучший {title}"] = f"{hero} ({value})"

        # Профиль (аватар, звание, элитный, флаг, последний вход, статус)
        ls_inside = soup_profile.find('div', class_='ls-inside')
        if ls_inside:
            img_tag = ls_inside.find('img')
            if img_tag:
                stats['Аватар'] = img_tag.get('src', '—')
                stats['Звание'] = img_tag.get('alt', '—')
        else:
            stats['Аватар'] = '—'
            stats['Звание'] = '—'

        last_seen = soup_profile.select_one("div.last-seen")
        stats['Последний вход'] = last_seen.text.strip() if last_seen else "—"

        uname_tag = soup_profile.find("h2", class_="profile-uname")
        stats["Элитный"] = "p-elite" in uname_tag.get("class", []) if uname_tag else False

        flag_img = soup_profile.find("img", class_="user--flag")
        if flag_img:
            flag_src = flag_img.get("src", "")
            flag_url_full = "https:" + flag_src if flag_src.startswith("//") else flag_src
            stats['Флаг'] = flag_url_full
        else:
            stats['Флаг'] = None



        # ======== Парсинг последних игр ========
        games = {}
        table = soup_dota.find("tbody", id="result-table")
        if table:
            rows = table.find_all("tr")
            for i, row in enumerate(rows):
                if i >= 5:
                    break
                cols = row.find_all("td")
                if len(cols) >= 5:
                    hero_span = cols[0].find("span")
                    hero = hero_span.text.strip() if hero_span else "—"
                    mode = cols[1].text.strip()
                    time = cols[2].text.strip()

                    kda_parts = cols[3].find_all("span")
                    k = kda_parts[0].text.strip() if len(kda_parts) > 0 else "—"
                    d = kda_parts[1].text.strip() if len(kda_parts) > 1 else "—"
                    a = kda_parts[2].text.strip() if len(kda_parts) > 2 else "—"
                    kda = f"{k}/{d}/{a}"

                    score_span = cols[4].find("span")
                    score_text = score_span.text.strip() if score_span else "—"

                    games[f"Игра {i + 1}"] = {
                        'hero': hero,
                        'mode': mode,
                        'time': time,
                        'kda': kda,
                        'score': score_text,
                    }
        stats["Последние игры"] = games

        return stats

    except Exception as e:
        return {'Ошибка': f"Произошла непредвиденная ошибка: {e}"}


# Пример вызова:
if __name__ == "__main__":
    nickname = "fng"
    from pprint import pprint

    result = fetch_iccup_stats(nickname)
    pprint(result)

    # Если флаг был скачан, можно его использовать
    if result.get('Флаг') and result.get('Флаг') != "None":
        download_flag(result['Флаг'])
        print(f"Флаг скачан: parsed-flag.png")