from modules.ext import Database

import aiosqlite
import discord

from typing import Union, List, Any, Optional

__all__ = [
    "Inventory"
]

TABLE_NAME = "inventory"  # Enter the table name here (tip:- use only lowercase letters)

shop_items = [
    {"name": "<:cs:1397687842779435068> бесплатный кс", "cost": 100, "id": 1, "info": "Бесплатный кс от администратора (халява)"},
    {"name": "<:color:1397688917083291709> смена цвета роли", "cost": 15750, "id": 2, "info": "Позволяет изменить цвет вашей роли на сервере"},
    {"name": "<:BTNSilence:1398024524330434773> анмут", "cost": 18500, "id": 3, "info": "Снять мут с себя в случае блокировки на голосовом канале"},
    {"name": "<:unban:1397687712051368067> разбан с клозов", "cost": 22599, "id": 4, "info": "Разбан в закрытых играх"},
    {"name": "<:role:1397687938099318906> особые права роли", "cost": 39999, "id": 5, "info": "Получить особые права для вашей роли (+1 доступ за покупку)"},
    {"name": "<:private:1397687676370681956> приватная комната", "cost": 50000, "id": 6, "info": "Возможность создать свою приватную комнату"},
    {"name": "<:zvuk:1397688038712283197> улучшенное качество звука", "cost": 68999, "id": 7, "info": "Увеличивает качество звука в приватной комнате"},
    {"name": "<:update:1396934490944962581> улучшенная роль", "cost": 79999, "id": 8, "info": "Роль от Bandit до Old Man, Улучшение текущей роли +1"},
    {"name": "<:BTNAdvancedUnholyArmor:1402048051404869702> Ладдер армор 14 дней", "cost": 105000, "id": 9, "info": "Ладдер армор на 14 дней"},
    {"name": "<:bonus:1402048692495585300> Ладдер бонус 14 дней", "cost": 115000, "id": 10, "info": "Ладдер бонус на 14 дней"},
    {"name": "<:proakk7:1397688074343026708> про акк 7 дней", "cost": 95000, "id": 11, "info": "Премиум аккаунт на 7 дней"},
    {"name": "<:proakk14:1397688101073195090> про акк 14 дней", "cost": 135000, "id": 12, "info": "Премиум аккаунт на 14 дней"},
    {"name": "<:proakk30:1397688130051637329> про акк 30 дней", "cost": 159000, "id": 13, "info": "Премиум аккаунт на 30 дней"},
    {"name": "<:pack30:1397687531935371435> супер пак 30 дней", "cost": 199999, "id": 14, "info": "Супер пакет: ладдер бонус и армор"},
    {"name": "<:sff:1396933372466692196> Shadow Fiend", "cost": 215999, "id": 15, "info": "Уникальная роль Shadow Fiend с особыми правами. Приносит 30 очков каждый день."},
    {"name": "<:necr:1396933406578708591> Necromancer", "cost": 275999, "id": 16, "info": "Уникальная роль Necromancer с особыми правами. Приносит 30 очков каждый день."},
    {"name": "<:majority:1396935174813520135> Majority", "cost": 375999, "id": 17, "info": "Уникальная роль Majority с особыми правами. Приносит 30 очков каждый день."},
    {"name": "<:royal:1398027190532309134> Royal Crown", "cost": 425999, "id": 18, "info": "Элитная роль Royal Crown с особыми правами."},
    {"name": "<:customerole:1397688173001310260> Своя роль", "cost": 750000, "id": 19, "info": "Создание своей роли с уникальным именем и особыми доступами, можно имя роли на русском языке"},
    {"name": "<:aegis:1397687748869095495> 1 аегис", "cost": 2000, "id": 20, "info": "Обменяйте 1000 <:gold:1396897616729735299> на 1 купон для сундука (аегис)"},
    {"name": "<:68:1396933324789776484> колесо фортуны", "cost": 20000, "id": 21, "info": "Доступ к колесу фортуны (10 аегисов)"},
    {"name": "<:tittle:1397687623845417030> титул на сайте (сезон)", "cost": 129999, "id": 22, "info": "Получите титул на сайте на текущий сезон"},
    {"name": "<:tittle:1397687623845417030> титул на сайте (навсегда)", "cost": 399999, "id": 23, "info": "Получите титул на сайте навсегда"},
    {"name": "🇪🇺 EU флаг", "cost": 999999, "id": 24, "info": "Уникальный EU флаг"}

]

item_names = [item["name"] for item in shop_items]


class Inventory:
    def __init__(self, database: Database):
        self._db = database

    @property
    def shop_items(self) -> List:
        return shop_items

    async def create_table(self) -> None:
        conn = await self._db.connect()
        await self._db.run(f"CREATE TABLE IF NOT EXISTS `{TABLE_NAME}`(userID BIGINT)", conn=conn)
        for col in item_names:
            try:
                await self._db.run(
                    f"ALTER TABLE `{TABLE_NAME}` ADD COLUMN `{col}` INTEGER DEFAULT 0",
                    conn=conn
                )
            except aiosqlite.OperationalError:
                pass

        await conn.close()

    async def open_acc(self, user: discord.Member) -> None:
        conn = await self._db.connect()
        data = await self._db.execute(
            f"SELECT * FROM `{TABLE_NAME}` WHERE userID = ?",
            (user.id,), fetch="one", conn=conn
        )
        if data is None:
            await self._db.run(
                f"INSERT INTO `{TABLE_NAME}`(userID) VALUES(?)",
                (user.id,), conn=conn
            )

        await conn.close()

    async def get_acc(self, user: discord.Member) -> Optional[Any]:
        users = await self._db.execute(
            f"SELECT * FROM `{TABLE_NAME}` WHERE userID = ?",
            (user.id,), fetch="one"
        )
        return users

    async def update_acc(
        self, user: discord.Member, amount: int, mode: str
    ) -> Optional[Any]:
        conn = await self._db.connect()
        data = await self._db.execute(
            f"SELECT * FROM `{TABLE_NAME}` WHERE userID = ?",
            (user.id,), fetch="one", conn=conn
        )
        if data is not None:
            await self._db.run(
                f"UPDATE `{TABLE_NAME}` SET `{mode}` = `{mode}` + ? WHERE userID = ?",
                (amount, user.id), conn=conn
            )

        users = await self._db.execute(
            f"SELECT `{mode}` FROM `{TABLE_NAME}` WHERE userID = ?",
            (user.id,), fetch="one", conn=conn
        )

        await conn.close()
        return users

    async def change_acc(self, user: discord.Member, amount: Union[int, None], mode: str) -> Optional[Any]:
        conn = await self._db.connect()
        data = await self._db.execute(
            f"SELECT * FROM `{TABLE_NAME}` WHERE userID = ?",
            (user.id,), fetch="one", conn=conn)
        if data is not None:
            await self._db.run(
                f"UPDATE `{TABLE_NAME}` SET `{mode}` = ? WHERE userID = ?",
                (amount, user.id), conn=conn
            )

        users = await self._db.execute(
            f"SELECT `{mode}` FROM `{TABLE_NAME}` WHERE userID = ?",
            (user.id,), fetch="one", conn=conn
        )

        await conn.close()
        return users
