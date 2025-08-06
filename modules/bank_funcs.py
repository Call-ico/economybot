from modules.ext import Database
from modules.balance_logger import write_balance_log, clean_old_logs

import aiosqlite
import discord
import asyncio

from typing import Any, Optional

__all__ = [
    "Bank"
]

TABLE_NAME = "bank"  # Enter the table name here (tip:- use only lowercase letters)
columns = ["wallet", "bank", "total_voice_minutes", "total_voice_gold", "total_messages", "total_message_gold"]  # Добавляем колонки для глобальной статистики


class Bank:
    def __init__(self, database: Database):
        self._db = database
        self._cleanup_task = None

    async def setup_log_cleaning(self):
        """Настраивает периодическую очистку логов"""
        async def clean_logs_task():
            while True:
                try:
                    # Очищаем логи раз в день
                    clean_old_logs()
                    await asyncio.sleep(24 * 60 * 60)  # 24 часа
                except Exception as e:
                    print(f"Ошибка при очистке логов: {e}")
                    await asyncio.sleep(60)  # Подождем минуту перед повторной попыткой

        self._cleanup_task = asyncio.create_task(clean_logs_task())

    async def create_table(self) -> None:
        conn = await self._db.connect()
        await self._db.run(f"CREATE TABLE IF NOT EXISTS `{TABLE_NAME}`(userID BIGINT)", conn=conn)
        for col in columns:
            try:
                await self._db.run(f"ALTER TABLE `{TABLE_NAME}` ADD COLUMN `{col}` BIGINT DEFAULT 0", conn=conn)
            except aiosqlite.OperationalError:
                pass

        await conn.close()

    async def open_acc(self, user: discord.Member) -> None:
        conn = await self._db.connect()
        data = await self._db.execute(
            f"SELECT * FROM `{TABLE_NAME}` WHERE userID = ?", (user.id,),
            fetch="one", conn=conn
        )

        if data is None:
            await self._db.run(
                f"INSERT INTO `{TABLE_NAME}`(userID, wallet) VALUES(?, ?)",
                (user.id, 0), conn=conn
            )

        await conn.close()

    async def get_acc(self, user: discord.Member) -> Optional[Any]:
        return await self._db.execute(
            f"SELECT * FROM `{TABLE_NAME}` WHERE userID = ?",
            (user.id,), fetch="one"
        )
        
    async def update_acc(
        self, user: discord.Member, amount: int = 0, mode: str = "wallet"
    ) -> Optional[Any]:
        """Добавляет указанную сумму к балансу пользователя"""
        await self.open_acc(user)  # Создаем аккаунт, если его нет
        
        conn = await self._db.connect()
        try:
            # Обновляем баланс
            await self._db.run(
                f"UPDATE `{TABLE_NAME}` SET `{mode}` = `{mode}` + ? WHERE userID = ?",
                (amount, user.id), conn=conn
            )
            
            # Получаем обновленное значение
            users = await self._db.execute(
                f"SELECT `{mode}` FROM `{TABLE_NAME}` WHERE userID = ?",
                (user.id,), fetch="one", conn=conn
            )
            
            # Логируем операцию в файл
            if users:
                write_balance_log(
                    f"Пользователь: {user.name} (ID: {user.id})\n"
                    f"Операция: {'+' if amount >= 0 else ''}{amount} {mode}\n"
                    f"Новый баланс: {users[0]}\n"
                    f"{'=' * 50}"
                )
            return users
            
        except Exception as e:
            print(f"Ошибка при обновлении баланса {user.name}: {e}")
            return None
            
        finally:
            await conn.close()

    async def reset_acc(self, user: discord.Member) -> None:
        await self._db.execute(f"DELETE FROM `{TABLE_NAME}` WHERE userID = ?", (user.id,))
        await self.open_acc(user)

    async def get_networth_lb(self) -> Any:
        """Получает отсортированный список пользователей по общему балансу"""
        return await self._db.execute(
            f"SELECT userID, wallet + bank as total FROM `{TABLE_NAME}` WHERE total > 0 ORDER BY total DESC",
            fetch="all"
        )
        
    async def update_leaderboard_message(self, client, channel_id: int, message_id: str = None):
        """Обновляет или создает сообщение с топом по балансу"""
        from modules.leaderboard_utils import create_balance_leaderboard_embed, create_balance_buttons
        
        try:
            # Получаем данные о балансах
            users_data = await self.get_networth_lb()
            if not users_data:
                return None
                
            # Создаем embed
            embed = await create_balance_leaderboard_embed(users_data, client)
            # Создаем кнопки
            view = create_balance_buttons()
            
            channel = client.get_channel(channel_id)
            if not channel:
                print(f"Канал {channel_id} не найден")
                return None
                
            if message_id:
                try:
                    # Пытаемся найти и обновить существующее сообщение
                    message = await channel.fetch_message(int(message_id))
                    await message.edit(embed=embed, view=view)
                    print(f"Обновлено сообщение топа {message.id}")
                    return message.id
                except discord.NotFound:
                    pass  # Сообщение не найдено, создадим новое
                    
            # Создаем новое сообщение
            message = await channel.send(embed=embed, view=view)
            print(f"Создано новое сообщение топа {message.id}")
            return message.id
            
        except Exception as e:
            print(f"Ошибка при обновлении топа: {e}")
            return None
        

