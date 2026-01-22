
from database import Database
from config import TASK_COOLDOWN_HOURS, ADMIN_IDS


# Инициализация базы данных
def init_database():
    db = Database()

    # Добавляем несколько тестовых текстов, если база пуста
    cursor = db.conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM texts')
    count = cursor.fetchone()['count']

    if count == 0:
        sample_texts = [
            "Отличный сервис! Рекомендую всем!",
            "Быстро и качественно, остался доволен",
            "Цены порадовали, буду обращаться еще",
            "Профессиональный подход, все понравилось",
            "Удобно, быстро, недорого. Что еще нужно?",
            "Лучший сервис в городе! Спасибо за работу!",
            "Все четко, без задержек, рекомендую",
            "Качественно выполнено, доволен результатом",
            "Вежливый персонал, хорошие цены",
            "Решили мою проблему быстро, спасибо!"
        ]

        for text in sample_texts:
            db.add_text(text)

        print(f"✅ Добавлено {len(sample_texts)} тестовых текстов в базу")

    # Проверяем структуру базы данных
    print("🔍 Проверка структуры базы данных...")

    # Проверяем наличие столбца is_admin в users
    try:
        cursor.execute('SELECT is_admin FROM users LIMIT 1')
        print("✅ Столбец is_admin существует в users")
    except:
        print("⚠️ Столбец is_admin отсутствует в users")
        print("🔄 Добавление столбца is_admin...")
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')

    # Проверяем наличие столбца hidden_until в tasks
    try:
        cursor.execute('SELECT hidden_until FROM tasks LIMIT 1')
        print("✅ Столбец hidden_until существует в tasks")
    except:
        print("⚠️ Столбец hidden_until отсутствует в tasks")
        print("🔄 Добавление столбца hidden_until...")
        cursor.execute('ALTER TABLE tasks ADD COLUMN hidden_until TIMESTAMP')

    # Проверяем наличие столбца crypto_type в payments
    try:
        cursor.execute('SELECT crypto_type FROM payments LIMIT 1')
        print("✅ Столбец crypto_type существует в payments")
    except:
        print("⚠️ Столбец crypto_type отсутствует в payments")
        print("🔄 Добавление столбца crypto_type...")
        cursor.execute('ALTER TABLE payments ADD COLUMN crypto_type TEXT')

    # Проверяем наличие столбца last_completed in tasks
    try:
        cursor.execute('SELECT last_completed FROM tasks LIMIT 1')
        print("✅ Столбец last_completed существует в tasks")
    except:
        print("⚠️ Столбец last_completed отсутствует в tasks")
        print("🔄 Добавление столбца last_completed...")
        cursor.execute('ALTER TABLE tasks ADD COLUMN last_completed TIMESTAMP')

    # Добавляем администраторов в базу, если их нет
    for admin_id in ADMIN_IDS:
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (admin_id,))
        if not cursor.fetchone():
            print(f"👑 Добавление администратора {admin_id} в базу...")
            cursor.execute('''
                INSERT INTO users (user_id, username, full_name, balance, registered_at, is_admin)
                VALUES (?, 'admin', 'Administrator', 0, datetime('now'), 1)
            ''', (admin_id,))

    db.conn.commit()

    print(f"✅ Настройка КД для заданий: {TASK_COOLDOWN_HOURS} часов")
    print(f"✅ Добавлено администраторов: {len(ADMIN_IDS)}")
    print("✅ База данных инициализирована")
    db.close()


if __name__ == '__main__':
    init_database()
