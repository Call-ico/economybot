# 📙Quickstart

# Method - 1

## clone the repository

```sh
git clone https://github.com/Modern-Realm/economy-bot-discord.py
```

## Setting up the working directory & installing packages

```sh
cd "economy-bot-discord.py/economy with aiosqlite"
pip install -r requirements.txt
```

**Note:** make sure to install **any one** of these package`(discord.py, py-cord or nextcord)`

### Provide the secret keys/values in `.env` file

## Running the bot

```sh
python main.py
```

🎉 Your discord bot should be online and ready to use!

# Method - 2

## Download the source file

- [click here](https://github.com/Modern-Realm/economy-bot-discord.py/releases/download/v3.0.7/economy.with.aiosqlite.zip)
to download the `zip` file.
- extract all the files & folders

## Install required packages

```shell
pip install -r requirements.txt
```

**Note:** make sure to install **any one** of these package`(discord.py, py-cord or nextcord)`

## Running the bot

```shell
python main.py
```

🎉 Your discord bot should be online and ready to use!

---

# Note: for discord.py users

**You can just clone [`branch:alpha`](https://github.com/Modern-Realm/economy-bot-discord.py/tree/alpha)**

```sh
git clone --single-branch -b alpha https://github.com/Modern-Realm/economy-bot-discord.py
```

**Or make some changes:**

- In `main.py`

  Make sure to uncomment the code where it has `await client.load_extension(...)`.

- In all `*.py` files in `cogs` folder

  Make sure to uncomment the code where the `setup(client)` is asynchronous

  i.e `async def setup(client)`

## Настройка переменных окружения

Создайте файл `.env` в этой папке и добавьте туда ваши токены и ключи:

```
TOKEN=ваш_токен_бота
COMMAND_PREFIX=!
FILENAME=database.db
# Добавьте другие токены и ключи по мере необходимости
```

## Система голосовых чатов

### Автоматический учет времени
- Бот автоматически отслеживает время, проведенное пользователями в голосовых каналах
- Учитываются **все голосовые каналы** на сервере
- Начисляется 1 голда за каждую минуту в голосовом чате
- Статистика обновляется в реальном времени

### Ежедневный сброс
- Статистика голосовых чатов **автоматически сбрасывается в 4:00 утра по МСК**
- Каждый день начинается с чистого листа
- Пользователи могут набирать время заново

### Топ-10 игроков
- Автоматически обновляется список топ-10 игроков по времени в голосовых чатах
- Отображается в канале с ID: `1398715376677818553`
- Показывает время в минутах и заработанную голду

### Команды
- `/статистика [@участник]` — показывает статистику пользователя (время в войсе, голда, сообщения)

## Админ-команды (баны)

- `/бан @user 1h причина` — забанить пользователя на 1 час (поддерживаются 1h, 30m, 2d и т.д.)
- `/банлист` — список всех забаненных и сколько времени осталось
- `/анбан @user` — снять бан с пользователя

Забаненные пользователи не могут использовать команды бота (кроме /банлист и /анбан). Информация о банах хранится в файле `bans.json` в корне проекта. Разбан происходит автоматически по истечении срока.
