import os
from datetime import datetime, timedelta

LOG_FILE = "balance_logs.txt"
LOG_RETENTION_DAYS = 7  # Хранить логи 7 дней

def write_balance_log(message: str):
    """Записывает сообщение в лог с временной меткой"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Ошибка при записи в лог: {e}")

def clean_old_logs():
    """Очищает устаревшие записи из лога"""
    if not os.path.exists(LOG_FILE):
        return
        
    try:
        # Читаем все строки
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # Определяем дату для фильтрации (неделю назад)
        cutoff_date = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
        
        # Фильтруем только актуальные записи
        current_logs = []
        for line in lines:
            try:
                # Извлекаем дату из строки лога
                log_date_str = line[1:20]  # "[2025-08-03 12:34:56]"
                log_date = datetime.strptime(log_date_str, "%Y-%m-%d %H:%M:%S")
                
                # Сохраняем только актуальные записи
                if log_date >= cutoff_date:
                    current_logs.append(line)
            except:
                # Если не удалось разобрать дату, оставляем запись
                current_logs.append(line)
        
        # Перезаписываем файл только с актуальными записями
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.writelines(current_logs)
            
    except Exception as e:
        print(f"Ошибка при очистке логов: {e}")
