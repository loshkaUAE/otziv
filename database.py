import sqlite3
import logging
from datetime import datetime, timedelta
from config import DB_PATH, TASK_COOLDOWN_HOURS, ADMIN_IDS

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.update_admin_balances()

    def update_admin_balances(self):
        """Обновляет балансы админов, если они не существуют в базе"""
        cursor = self.conn.cursor()
        for admin_id in ADMIN_IDS:
            cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (admin_id,))
            if not cursor.fetchone():
                # Добавляем админа в базу
                cursor.execute('''
                    INSERT INTO users (user_id, username, full_name, balance, registered_at, is_admin)
                    VALUES (?, 'admin', 'Administrator', 0, ?, 1)
                ''', (admin_id, datetime.now()))
        self.conn.commit()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Пользователи (добавлено поле is_admin)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance REAL DEFAULT 0,
                completed_tasks INTEGER DEFAULT 0,
                pending_reviews INTEGER DEFAULT 0,
                registered_at TIMESTAMP,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                is_admin BOOLEAN DEFAULT 0
            )
        ''')

        # Задания (добавлено hidden_until для КД)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                link TEXT,
                total_count INTEGER,
                done_count INTEGER DEFAULT 0,
                price_per_review REAL,
                created_at TIMESTAMP,
                status TEXT DEFAULT 'active',
                hidden_until TIMESTAMP,
                last_completed TIMESTAMP
            )
        ''')

        # Отзывы на проверку
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_id INTEGER,
                text TEXT,
                screenshot_file_id TEXT,
                status TEXT DEFAULT 'pending',
                submitted_at TIMESTAMP,
                checked_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (task_id) REFERENCES tasks (task_id)
            )
        ''')

        # Выплаты (добавлено crypto_type для крипто-вывода)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                requisites TEXT,
                crypto_type TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP,
                paid_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Тексты для отзывов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS texts (
                text_id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                used_count INTEGER DEFAULT 0
            )
        ''')

        # Реферальные связи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER,
                referred_id INTEGER,
                level INTEGER,
                earned REAL DEFAULT 0,
                PRIMARY KEY (referrer_id, referred_id)
            )
        ''')

        # Связь заданий и текстов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_texts (
                task_id INTEGER,
                text_id INTEGER,
                PRIMARY KEY (task_id, text_id)
            )
        ''')

        # Задания взятые пользователями
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_tasks (
                user_id INTEGER,
                task_id INTEGER,
                taken_at TIMESTAMP,
                status TEXT DEFAULT 'taken',
                completed_at TIMESTAMP,
                PRIMARY KEY (user_id, task_id)
            )
        ''')

        # Добавляем столбец is_admin, если его нет
        try:
            cursor.execute('SELECT is_admin FROM users LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')

        self.conn.commit()

    # Методы для пользователей
    def add_user(self, user_id, username, full_name, referral_code=None, referred_by=None, is_admin=False):
        cursor = self.conn.cursor()

        if referral_code is None:
            import random
            import string
            referral_code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        # Проверяем, является ли пользователь админом
        if is_admin or user_id in ADMIN_IDS:
            admin_status = 1
        else:
            admin_status = 0

        try:
            cursor.execute('''
                INSERT INTO users (user_id, username, full_name, registered_at, referral_code, referred_by, is_admin)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, full_name, datetime.now(), referral_code, referred_by, admin_status))

            if referred_by:
                cursor.execute('''
                    INSERT INTO referrals (referrer_id, referred_id, level)
                    VALUES (?, ?, 1)
                ''', (referred_by, user_id))

                # Находим реферера 2 уровня
                cursor.execute('SELECT referred_by FROM users WHERE user_id = ?', (referred_by,))
                result = cursor.fetchone()
                if result and result['referred_by']:
                    cursor.execute('''
                        INSERT OR IGNORE INTO referrals (referrer_id, referred_id, level)
                        VALUES (?, ?, 2)
                    ''', (result['referred_by'], user_id))

            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Если пользователь уже существует, обновляем информацию
            cursor.execute('''
                UPDATE users SET username = ?, full_name = ?, is_admin = ? WHERE user_id = ?
            ''', (username, full_name, admin_status, user_id))
            self.conn.commit()
            return True

    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()

    def update_user_balance(self, user_id, amount):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        self.conn.commit()

    # Методы для заданий с учетом КД
    def add_task(self, category, link, total_count, price_per_review):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (category, link, total_count, price_per_review, created_at, hidden_until)
            VALUES (?, ?, ?, ?, ?, NULL)
        ''', (category, link, total_count, price_per_review, datetime.now()))

        task_id = cursor.lastrowid
        self.conn.commit()
        return task_id

    def get_active_tasks_for_user(self, user_id):
        """Получаем задания для конкретного пользователя с учетом КД и уже взятых"""
        cursor = self.conn.cursor()

        # Получаем все активные задания, не на кулдауне
        cursor.execute('''
            SELECT t.* FROM tasks t
            WHERE t.status = 'active' 
              AND t.done_count < t.total_count
              AND (t.hidden_until IS NULL OR t.hidden_until < ?)
            ORDER BY t.created_at DESC
        ''', (datetime.now(),))

        all_tasks = cursor.fetchall()

        # Получаем задания, которые пользователь уже брал
        cursor.execute('''
            SELECT task_id FROM user_tasks 
            WHERE user_id = ? AND status IN ('taken', 'completed')
        ''', (user_id,))
        user_task_ids = [row['task_id'] for row in cursor.fetchall()]

        # Фильтруем задания
        available_tasks = [task for task in all_tasks if task['task_id'] not in user_task_ids]
        return available_tasks

    def get_all_tasks(self):
        """Получает все задания"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM tasks ORDER BY task_id DESC')
        return cursor.fetchall()

    def get_task(self, task_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
        return cursor.fetchone()

    def update_task(self, task_id, field, value):
        cursor = self.conn.cursor()
        cursor.execute(f'UPDATE tasks SET {field} = ? WHERE task_id = ?', (value, task_id))
        self.conn.commit()

    def increment_task_done(self, task_id):
        cursor = self.conn.cursor()

        # Увеличиваем счетчик выполненных
        cursor.execute('''
            UPDATE tasks 
            SET done_count = done_count + 1,
                last_completed = ?
            WHERE task_id = ? AND done_count < total_count
        ''', (datetime.now(), task_id))

        # Проверяем, выполнено ли задание полностью
        cursor.execute('SELECT total_count, done_count FROM tasks WHERE task_id = ?', (task_id,))
        task = cursor.fetchone()

        if task and task['done_count'] >= task['total_count']:
            # Устанавливаем кулдаун 48 часов
            hidden_until = datetime.now() + timedelta(hours=TASK_COOLDOWN_HOURS)
            cursor.execute('''
                UPDATE tasks 
                SET status = 'completed',
                    hidden_until = ?
                WHERE task_id = ? AND done_count >= total_count
            ''', (hidden_until, task_id))

        self.conn.commit()

    # Методы для работы с взятыми заданиями
    def add_user_task(self, user_id, task_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO user_tasks (user_id, task_id, taken_at, status)
                VALUES (?, ?, ?, 'taken')
            ''', (user_id, task_id, datetime.now()))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user_tasks(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ut.*, t.category, t.link, t.price_per_review
            FROM user_tasks ut
            JOIN tasks t ON ut.task_id = t.task_id
            WHERE ut.user_id = ?
            ORDER BY ut.taken_at DESC
        ''', (user_id,))
        return cursor.fetchall()

    # Методы для текстов
    def add_text(self, content):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO texts (content) VALUES (?)', (content,))
        self.conn.commit()
        return cursor.lastrowid

    def get_texts(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM texts ORDER BY text_id')
        return cursor.fetchall()

    def delete_text(self, text_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM texts WHERE text_id = ?', (text_id,))
        self.conn.commit()

    # Методы для отзывов с пагинацией
    def add_review(self, user_id, task_id, text, screenshot_file_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO reviews (user_id, task_id, text, screenshot_file_id, submitted_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, task_id, text, screenshot_file_id, datetime.now()))

        cursor.execute('UPDATE users SET pending_reviews = pending_reviews + 1 WHERE user_id = ?', (user_id,))

        review_id = cursor.lastrowid
        self.conn.commit()
        return review_id

    def get_pending_reviews_paginated(self, offset=0, limit=1):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT r.*, u.username, u.full_name, t.category, t.link
            FROM reviews r
            JOIN users u ON r.user_id = u.user_id
            JOIN tasks t ON r.task_id = t.task_id
            WHERE r.status = 'pending'
            ORDER BY r.submitted_at
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        return cursor.fetchall()

    def get_pending_reviews_count(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM reviews WHERE status = "pending"')
        return cursor.fetchone()['count']

    def get_pending_review_by_index(self, index):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT r.*, u.username, u.full_name, t.category, t.link
            FROM reviews r
            JOIN users u ON r.user_id = u.user_id
            JOIN tasks t ON r.task_id = t.task_id
            WHERE r.status = 'pending'
            ORDER BY r.submitted_at
            LIMIT 1 OFFSET ?
        ''', (index,))
        return cursor.fetchone()

    def approve_review(self, review_id):
        cursor = self.conn.cursor()

        # Получаем информацию об отзыве
        cursor.execute('''
            SELECT r.user_id, r.task_id, t.price_per_review
            FROM reviews r
            JOIN tasks t ON r.task_id = t.task_id
            WHERE r.review_id = ?
        ''', (review_id,))
        review = cursor.fetchone()

        if not review:
            return False

        user_id = review['user_id']
        task_id = review['task_id']
        price = review['price_per_review']

        # Обновляем статус отзыва
        cursor.execute('''
            UPDATE reviews 
            SET status = 'approved', checked_at = ?
            WHERE review_id = ?
        ''', (datetime.now(), review_id))

        # Начисляем деньги исполнителю
        cursor.execute(
            'UPDATE users SET balance = balance + ?, completed_tasks = completed_tasks + 1 WHERE user_id = ?',
            (price, user_id))

        # Уменьшаем количество отзывов на проверке
        cursor.execute('UPDATE users SET pending_reviews = pending_reviews - 1 WHERE user_id = ?', (user_id,))

        # Обновляем счетчик выполненных в задании
        self.increment_task_done(task_id)

        # Отмечаем задание как выполненное для пользователя
        cursor.execute('''
            UPDATE user_tasks 
            SET status = 'completed', completed_at = ?
            WHERE user_id = ? AND task_id = ?
        ''', (datetime.now(), user_id, task_id))

        # Начисляем реферальные бонусы
        cursor.execute('''
            SELECT referrer_id, level FROM referrals WHERE referred_id = ?
        ''', (user_id,))

        referrals = cursor.fetchall()
        for ref in referrals:
            referrer_id = ref['referrer_id']
            level = ref['level']

            if level == 1:
                bonus = price * 0.10
            else:
                bonus = price * 0.05

            cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bonus, referrer_id))
            cursor.execute('UPDATE referrals SET earned = earned + ? WHERE referrer_id = ? AND referred_id = ?',
                           (bonus, referrer_id, user_id))

        self.conn.commit()
        return True

    def reject_review(self, review_id):
        cursor = db.conn.cursor()
        cursor.execute('SELECT user_id, task_id FROM reviews WHERE review_id = ?', (review_id,))
        review = cursor.fetchone()

        if review:
            cursor.execute('''
                UPDATE reviews 
                SET status = 'rejected', checked_at = ?
                WHERE review_id = ?
            ''', (datetime.now(), review_id))

            cursor.execute('UPDATE users SET pending_reviews = pending_reviews - 1 WHERE user_id = ?',
                           (review['user_id'],))

            # Разблокируем задание для пользователя
            cursor.execute('''
                DELETE FROM user_tasks 
                WHERE user_id = ? AND task_id = ? AND status = 'taken'
            ''', (review['user_id'], review['task_id']))

            self.conn.commit()

    # Методы для выплат с пагинацией
    def add_payment(self, user_id, amount, requisites, crypto_type=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO payments (user_id, amount, requisites, crypto_type, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, amount, requisites, crypto_type, datetime.now()))

        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))

        payment_id = cursor.lastrowid
        self.conn.commit()
        return payment_id

    def get_pending_payments_paginated(self, offset=0, limit=1):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT p.*, u.username, u.full_name
            FROM payments p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'pending'
            ORDER BY p.created_at
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        return cursor.fetchall()

    def get_pending_payments_count(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM payments WHERE status = "pending"')
        return cursor.fetchone()['count']

    def get_pending_payment_by_index(self, index):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT p.*, u.username, u.full_name
            FROM payments p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'pending'
            ORDER BY p.created_at
            LIMIT 1 OFFSET ?
        ''', (index,))
        return cursor.fetchone()

    def approve_payment(self, payment_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE payments 
            SET status = 'paid', paid_at = ?
            WHERE payment_id = ?
        ''', (datetime.now(), payment_id))
        self.conn.commit()

    # Методы для статистики
    def get_statistics(self):
        cursor = self.conn.cursor()

        cursor.execute('SELECT COUNT(*) as count FROM users')
        users_count = cursor.fetchone()['count']

        cursor.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "active"')
        active_tasks = cursor.fetchone()['count']

        cursor.execute('SELECT COUNT(*) as count FROM reviews WHERE status = "approved"')
        completed_reviews = cursor.fetchone()['count']

        cursor.execute('SELECT SUM(balance) as total FROM users')
        total_balance = cursor.fetchone()['total'] or 0

        cursor.execute('SELECT COUNT(*) as count FROM reviews WHERE status = "pending"')
        pending_reviews = cursor.fetchone()['count']

        cursor.execute('SELECT COUNT(*) as count FROM payments WHERE status = "pending"')
        pending_payments = cursor.fetchone()['count']

        cursor.execute('''
            SELECT u.user_id, u.username, u.balance
            FROM users u
            ORDER BY u.balance DESC
            LIMIT 10
        ''')
        top_users = cursor.fetchall()

        # Общее количество отзывов
        cursor.execute('SELECT COUNT(*) as count FROM reviews')
        total_reviews = cursor.fetchone()['count']

        # Статистика выплат
        cursor.execute('SELECT COUNT(*) as count, SUM(amount) as total FROM payments WHERE status = "paid"')
        payment_stats = cursor.fetchone()
        paid_payments = payment_stats['count'] or 0
        paid_total = payment_stats['total'] or 0

        # Статистика балансов админов
        admin_ids_str = ','.join(str(id) for id in ADMIN_IDS)
        if admin_ids_str:
            cursor.execute(f'SELECT SUM(balance) as total FROM users WHERE user_id IN ({admin_ids_str})')
        else:
            cursor.execute('SELECT 0 as total')
        admin_balance = cursor.fetchone()['total'] or 0

        # Топ недели
        cursor.execute('''
            SELECT u.username, COUNT(r.review_id) as count 
            FROM reviews r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.status = 'approved' AND r.checked_at >= datetime('now', '-7 days')
            GROUP BY r.user_id
            ORDER BY count DESC
            LIMIT 3
        ''')
        top_weekly = cursor.fetchall()

        # Топ месяца
        cursor.execute('''
            SELECT u.username, COUNT(r.review_id) as count 
            FROM reviews r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.status = 'approved' AND r.checked_at >= datetime('now', '-30 days')
            GROUP BY r.user_id
            ORDER BY count DESC
            LIMIT 3
        ''')
        top_monthly = cursor.fetchall()

        return {
            'users_count': users_count,
            'active_tasks': active_tasks,
            'completed_reviews': completed_reviews,
            'total_balance': total_balance,
            'pending_reviews': pending_reviews,
            'pending_payments': pending_payments,
            'top_users': top_users,
            'total_reviews': total_reviews,
            'paid_payments': paid_payments,
            'paid_total': paid_total,
            'admin_balance': admin_balance,
            'top_weekly': top_weekly,
            'top_monthly': top_monthly
        }

    def close(self):
        self.conn.close()

