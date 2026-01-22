
import logging
import re
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, \
    CallbackQueryHandler
from config import ADMIN_IDS, PRICES, MIN_WITHDRAW, SUPPORT_USERNAME, NEWS_CHANNEL
from database import Database
from keyboards import *
from datetime import datetime, timedelta
from telegram.helpers import escape_markdown

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для диалогов
WITHDRAW_TYPE, WITHDRAW_AMOUNT, WITHDRAW_REQUISITES, CRYPTO_ADDRESS = range(4)
ADD_TEXT = range(1)
CONFIRM_TASK_TAKE = range(1)
TASK_EDIT_MENU, TASK_EDIT_CHOOSE, TASK_EDIT_FIELD, TASK_EDIT_VALUE = range(4, 8)

db = Database()


def is_admin(user_id):
    return user_id in ADMIN_IDS


def format_balance(balance):
    """Форматирование баланса"""
    return f"{balance:.2f}".rstrip('0').rstrip('.')


def register_user_if_needed(update: Update):
    """Регистрирует пользователя, если он не зарегистрирован"""
    user = update.effective_user
    user_id = user.id

    existing_user = db.get_user(user_id)
    if not existing_user:
        # Регистрируем пользователя
        db.add_user(user_id, user.username, user.full_name)
    return True


# Команда /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # Проверяем реферальный код
    referral_code = None
    if context.args and len(context.args) > 0:
        referral_code = context.args[0]

    # Ищем пользователя по реферальному коду
    referred_by = None
    if referral_code:
        cursor = db.conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
        result = cursor.fetchone()
        if result:
            referred_by = result['user_id']

    # Проверяем, существует ли пользователь
    existing_user = db.get_user(user_id)

    if not existing_user:
        # Добавляем пользователя
        success = db.add_user(user_id, user.username, user.full_name, referred_by=referred_by)
        welcome_type = "new"
    else:
        # Обновляем информацию о пользователе
        cursor = db.conn.cursor()
        cursor.execute('''
            UPDATE users SET username = ?, full_name = ? WHERE user_id = ?
        ''', (user.username, user.full_name, user_id))
        db.conn.commit()
        success = True
        welcome_type = "returning"

    if welcome_type == "new":
        welcome_text = f"""
👋 Добро пожаловать, {user.full_name}!

📋 Бот для заработка на отзывах:
• Берете задания
• Оставляете отзывы
• Получаете деньги

💰 Цены за отзыв:
• Яндекс Карты: {PRICES['yandex']}₽
• 2ГИС: {PRICES['2gis']}₽
• Другое: {PRICES['other']}₽

👥 Реферальная система:
• Уровень 1: 10% от заработка
• Уровень 2: 5% от заработка

💸 Минимальный вывод: {MIN_WITHDRAW}₽

📞 Поддержка: {SUPPORT_USERNAME}
📰 Новости: {NEWS_CHANNEL}

Используйте кнопки ниже для навигации:
"""
    else:
        # Получаем обновленные данные пользователя
        user_data = db.get_user(user_id)
        balance = format_balance(user_data['balance']) if user_data else "0"

        welcome_text = f"""
👋 С возвращением, {user.full_name}!

Ваш баланс: {balance}₽

📞 Поддержка: {SUPPORT_USERNAME}
📰 Новости: {NEWS_CHANNEL}

Используйте кнопки ниже для навигации:
"""

    keyboard = get_main_keyboard(user_id, is_admin(user_id))
    await update.message.reply_text(welcome_text, reply_markup=keyboard)


# Команда /admin
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет доступа к админ-панели")
        return

    keyboard = get_admin_keyboard()
    await update.message.reply_text("👑 Админ-панель", reply_markup=keyboard)


# Команда /tasks
async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user_if_needed(update)
    user_id = update.effective_user.id
    tasks = db.get_active_tasks_for_user(user_id)

    if not tasks:
        await update.message.reply_text("📭 На данный момент нет доступных заданий")
        return

    text = "📋 ДОСТУПНЫЕ ЗАДАНИЯ:\n\n"
    for i, task in enumerate(tasks, 1):
        remaining = task['total_count'] - task['done_count']
        text += f"Задание #{task['task_id']}\n"
        text += f"• Категория: {task['category']}\n"
        text += f"• Ссылка: {task['link']}\n"
        text += f"• Осталось мест: {remaining}/{task['total_count']}\n"
        text += f"• Цена: {task['price_per_review']}₽ за отзыв\n\n"

    keyboard = get_tasks_keyboard(tasks)
    await update.message.reply_text(text, reply_markup=keyboard)


# Команда /profile
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user_if_needed(update)
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден. Попробуйте /start")
        return

    # Получаем реферальную статистику
    cursor = db.conn.cursor()
    cursor.execute('SELECT COUNT(*) as count, SUM(earned) as total FROM referrals WHERE referrer_id = ?', (user_id,))
    ref_stats = cursor.fetchone()

    # Получаем статистику заданий
    cursor.execute('''
        SELECT COUNT(*) as count FROM reviews 
        WHERE user_id = ? AND status = 'approved'
    ''', (user_id,))
    approved_reviews = cursor.fetchone()['count']

    cursor.execute('''
        SELECT COUNT(*) as count FROM reviews 
        WHERE user_id = ? AND status = 'pending'
    ''', (user_id,))
    pending_reviews = cursor.fetchone()['count']

    # Получаем взятые задания
    user_tasks = db.get_user_tasks(user_id)

    text = f"""
👤 ВАШ ПРОФИЛЬ:

ID: {user['user_id']}
Имя: {user['full_name']}
Баланс: {format_balance(user['balance'])}₽
Выполнено заданий: {approved_reviews}
На проверке: {pending_reviews}
Взято заданий: {len(user_tasks)}

👥 РЕФЕРАЛЫ:
Приглашено: {ref_stats['count'] or 0} человек
Заработано с рефералов: {format_balance(ref_stats['total'] or 0)}₽
Ваша реферальная ссылка: t.me/{context.bot.username}?start={user['referral_code']}

💡 Чтобы пригласить друга, отправьте ему ссылку выше.
    """

    await update.message.reply_text(text)


# Кнопка "Выход" - возврат в главное меню
async def exit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = get_main_keyboard(user_id, is_admin(user_id))
    await update.message.reply_text("🏠 Возвращаемся в главное меню...", reply_markup=keyboard)


# Функция для получения статистики отзывов и выплат
def get_extended_statistics():
    cursor = db.conn.cursor()

    # Общее количество отзывов (всех статусов)
    cursor.execute('SELECT COUNT(*) as count FROM reviews')
    total_reviews = cursor.fetchone()['count']

    # Количество одобренных отзывов
    cursor.execute('SELECT COUNT(*) as count FROM reviews WHERE status = "approved"')
    approved_reviews = cursor.fetchone()['count']

    # Количество отклоненных отзывов
    cursor.execute('SELECT COUNT(*) as count FROM reviews WHERE status = "rejected"')
    rejected_reviews = cursor.fetchone()['count']

    # Статистика по выплатам
    cursor.execute('SELECT COUNT(*) as count, SUM(amount) as total FROM payments WHERE status = "paid"')
    payment_stats = cursor.fetchone()
    paid_payments = payment_stats['count'] or 0
    paid_total = payment_stats['total'] or 0

    # Статистика по балансам админов
    if ADMIN_IDS:
        cursor.execute(
            'SELECT SUM(balance) as total FROM users WHERE user_id IN ({})'.format(','.join('?' for _ in ADMIN_IDS)),
            ADMIN_IDS)
        admin_balance = cursor.fetchone()['total'] or 0
    else:
        admin_balance = 0

    return {
        'total_reviews': total_reviews,
        'approved_reviews': approved_reviews,
        'rejected_reviews': rejected_reviews,
        'paid_payments': paid_payments,
        'paid_total': paid_total,
        'admin_balance': admin_balance
    }


# Обработчик вывода средств
async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user_if_needed(update)
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден. Попробуйте /start")
        return ConversationHandler.END

    if user['balance'] < MIN_WITHDRAW:
        await update.message.reply_text(
            f"❌ Минимальная сумма для вывода: {MIN_WITHDRAW}₽\nВаш баланс: {format_balance(user['balance'])}₽")
        return ConversationHandler.END

    context.user_data['withdraw_user_id'] = user_id
    keyboard = get_withdraw_type_keyboard()
    await update.message.reply_text(
        f"💰 Ваш баланс: {format_balance(user['balance'])}₽\n\nВыберите способ вывода:",
        reply_markup=keyboard
    )

    return WITHDRAW_TYPE


# Обработка выбора типа вывода
async def withdraw_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'withdraw_card':
        context.user_data['withdraw_type'] = 'card'
        await query.edit_message_text(
            f"💳 Вывод на банковскую карту\n\nВведите сумму для вывода (минимум {MIN_WITHDRAW}₽):"
        )
        return WITHDRAW_AMOUNT
    elif query.data == 'withdraw_crypto':
        context.user_data['withdraw_type'] = 'crypto'
        await query.edit_message_text(
            f"💎 Вывод криптовалютой (TON)\n\nВведите сумму для вывода (минимум {MIN_WITHDRAW}₽):"
        )
        return WITHDRAW_AMOUNT
    elif query.data == 'cancel':
        await query.edit_message_text("❌ Вывод отменен")
        return ConversationHandler.END


# Обработка суммы вывода
async def withdraw_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(',', '.'))
        user_id = context.user_data['withdraw_user_id']
        user = db.get_user(user_id)

        if amount < MIN_WITHDRAW:
            await update.message.reply_text(f"❌ Минимальная сумма: {MIN_WITHDRAW}₽")
            return WITHDRAW_AMOUNT

        if amount > user['balance']:
            await update.message.reply_text(f"❌ Недостаточно средств. Ваш баланс: {format_balance(user['balance'])}₽")
            return WITHDRAW_AMOUNT

        context.user_data['withdraw_amount'] = amount
        withdraw_type = context.user_data.get('withdraw_type', 'card')

        if withdraw_type == 'card':
            await update.message.reply_text("💳 Введите реквизиты карты (номер карты):")
            return WITHDRAW_REQUISITES
        else:
            await update.message.reply_text("💎 Введите адрес кошелька TON:")
            return CRYPTO_ADDRESS
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите число")
        return WITHDRAW_AMOUNT


# Обработка реквизитов карты
async def withdraw_requisites_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requisites = update.message.text.strip()
    amount = context.user_data['withdraw_amount']
    user_id = context.user_data['withdraw_user_id']

    if not requisites or len(requisites) < 16:
        await update.message.reply_text("❌ Пожалуйста, введите корректный номер карты (16-19 цифр)")
        return WITHDRAW_REQUISITES

    payment_id = db.add_payment(user_id, amount, requisites, 'card')

    text = f"""
💸 ЗАЯВКА СОЗДАНА:

Сумма: {format_balance(amount)}₽
Способ: Банковская карта
Реквизиты: {requisites}
Статус: ⏳ Ожидает выплаты
Примерное время: 1-24 часа

Ваш баланс уменьшен на {format_balance(amount)}₽
"""

    await update.message.reply_text(text)

    # Уведомляем администратора
    user = db.get_user(user_id)
    username = user['username'] or user['full_name']

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"💰 НОВАЯ ЗАЯВКА НА ВЫВОД\n\n"
                f"ID: {payment_id}\n"
                f"От: @{username}\n"
                f"Сумма: {format_balance(amount)}₽\n"
                f"Способ: Банковская карта\n"
                f"Реквизиты: {requisites}"
            )
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")

    # Очищаем данные
    context.user_data.clear()

    return ConversationHandler.END


# Обработка адреса крипто-кошелька
async def crypto_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    amount = context.user_data['withdraw_amount']
    user_id = context.user_data['withdraw_user_id']

    if not address:
        await update.message.reply_text("❌ Пожалуйста, введите адрес кошелька TON")
        return CRYPTO_ADDRESS

    payment_id = db.add_payment(user_id, amount, address, 'TON')

    text = f"""
💎 ЗАЯВКА НА КРИПТО-ВЫВОД:

Сумма: {format_balance(amount)}₽
Криптовалюта: TON
Адрес кошелька: {address}
Статус: ⏳ Ожидает выплаты
Примерное время: 1-12 часов

Ваш баланс уменьшен на {format_balance(amount)}₽
"""

    await update.message.reply_text(text)

    # Уведомляем администратора
    user = db.get_user(user_id)
    username = user['username'] or user['full_name']

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"💎 НОВАЯ ЗАЯВКА НА КРИПТО-ВЫВОД\n\n"
                f"ID: {payment_id}\n"
                f"От: @{username}\n"
                f"Сумма: {format_balance(amount)}₽\n"
                f"Криптовалюта: TON\n"
                f"Адрес: {address}"
            )
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")

    # Очищаем данные
    context.user_data.clear()

    return ConversationHandler.END


# Команда /referral
async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user_if_needed(update)
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден. Попробуйте /start")
        return

    text = f"""
👥 РЕФЕРАЛЬНАЯ СИСТЕМА:

Ваша реферальная ссылка:
https://t.me/{context.bot.username}?start={user['referral_code']}

Или просто отправьте команду:
/start {user['referral_code']}

🎯 Как это работает:
1. Вы приглашаете друга по ссылке
2. Он регистрируется и начинает работать
3. Вы получаете 10% от его заработка
4. Если он пригласит друга - вы получаете 5% от заработка того, кого он пригласил

💸 Уже заработано с рефералов:
• Уровень 1 (10%): смотрите в профиле
• Уровень 2 (5%): смотрите в профиле

📈 Приглашайте друзей и увеличивайте свой доход!
"""

    await update.message.reply_text(text)


# Обновленный обработчик админ-панели с новой статистикой
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("⛔ У вас нет доступа")
        return

    data = query.data

    if data == 'add_task':
        keyboard = get_category_keyboard()
        await query.edit_message_text("📌 Выберите категорию задания:", reply_markup=keyboard)

    elif data.startswith('cat_'):
        category = data.split('_')[1]
        if category == 'yandex':
            price = PRICES['yandex']
            category_name = 'Яндекс Карты'
        elif category == '2gis':
            price = PRICES['2gis']
            category_name = '2ГИС'
        else:
            price = PRICES['other']
            category_name = 'Другое'

        # Сохраняем данные в user_data для дальнейших шагов
        context.user_data['admin_task'] = {
            'category': category_name,
            'price': price,
            'step': 'link'
        }

        await query.edit_message_text(
            f"📌 Категория: {category_name}\n"
            f"💰 Цена за отзыв: {price}₽\n\n"
            f"Введите ссылку на сайт:"
        )

    elif data == 'statistics':
        stats = db.get_statistics()
        extended_stats = get_extended_statistics()

        # Получаем топ недели и месяца
        cursor = db.conn.cursor()

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

        text = f"""
📊 ОБЩАЯ СТАТИСТИКА:

👥 Исполнителей: {stats['users_count']}
📋 Активных заданий: {stats['active_tasks']}
✅ Выполнено отзывов: {stats['completed_reviews']} (всего: {extended_stats['total_reviews']})
❌ Отклонено отзывов: {extended_stats['rejected_reviews']}
💰 На балансах: {format_balance(stats['total_balance'])}₽
⏳ На проверке: {stats['pending_reviews']} отзывов
💸 Ждут выплаты: {stats['pending_payments']} заявок

💳 ВЫПЛАТЫ:
Выплачено: {extended_stats['paid_payments']} заявок
Общая сумма выплат: {format_balance(extended_stats['paid_total'])}₽

💰 БАЛАНСЫ АДМИНОВ:
Общий баланс админов: {format_balance(extended_stats['admin_balance'])}₽

🏆 ТОП НЕДЕЛИ:
"""
        if top_weekly:
            for i, top in enumerate(top_weekly, 1):
                username = top['username'] or f"Пользователь {i}"
                text += f"{i}. {username} - {top['count']} отзывов\n"
        else:
            text += "Нет данных за неделю\n"

        text += "\n🏆 ТОП МЕСЯЦА:\n"
        if top_monthly:
            for i, top in enumerate(top_monthly, 1):
                username = top['username'] or f"Пользователь {i}"
                text += f"{i}. {username} - {top['count']} отзывов\n"
        else:
            text += "Нет данных за месяц\n"

        text += f"\n💳 Топ исполнителей по балансу:"
        for i, user in enumerate(stats['top_users'], 1):
            username = user['username'] or f"Пользователь {user['user_id']}"
            text += f"\n{i}. {username} - {format_balance(user['balance'])}₽"

        keyboard = get_back_to_admin_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)

    elif data == 'top_stats':
        # Показываем только топы
        cursor = db.conn.cursor()

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

        text = "🏆 ТОП ИСПОЛНИТЕЛЕЙ\n\n"

        text += "🔥 ТОП НЕДЕЛИ:\n"
        if top_weekly:
            for i, top in enumerate(top_weekly, 1):
                username = top['username'] or f"Пользователь {i}"
                text += f"{i}. {username} - {top['count']} отзывов\n"
        else:
            text += "Нет данных за неделю\n"

        text += "\n📈 ТОП МЕСЯЦА:\n"
        if top_monthly:
            for i, top in enumerate(top_monthly, 1):
                username = top['username'] or f"Пользователь {i}"
                text += f"{i}. {username} - {top['count']} отзывов\n"
        else:
            text += "Нет данных за месяц"

        keyboard = get_back_to_admin_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)

    elif data == 'edit_tasks':
        # Показываем список заданий для редактирования
        cursor = db.conn.cursor()
        cursor.execute('''
            SELECT * FROM tasks 
            WHERE status = 'active' OR status = 'completed'
            ORDER BY task_id DESC
        ''')
        tasks = cursor.fetchall()

        if not tasks:
            await query.edit_message_text("📭 Нет заданий для редактирования")
            return

        text = "📝 ВЫБЕРИТЕ ЗАДАНИЕ ДЛЯ РЕДАКТИРОВАНИЯ:\n\n"
        for task in tasks:
            remaining = task['total_count'] - task['done_count']
            status_icon = "✅" if task['status'] == 'completed' else "🟢"
            text += f"{status_icon} Задание #{task['task_id']}\n"
            text += f"• Категория: {task['category']}\n"
            text += f"• Осталось: {remaining}/{task['total_count']}\n"
            text += f"• Цена: {task['price_per_review']}₽\n"
            text += f"• Статус: {'Завершено' if task['status'] == 'completed' else 'Активно'}\n\n"

        keyboard = get_edit_tasks_keyboard(tasks)
        await query.edit_message_text(text, reply_markup=keyboard)

    elif data.startswith('edit_task_'):
        task_id = int(data.split('_')[2])
        task = db.get_task(task_id)

        if not task:
            await query.edit_message_text("❌ Задание не найдено")
            return

        context.user_data['editing_task'] = task_id

        text = f"""
✏️ РЕДАКТИРОВАНИЕ ЗАДАНИЯ #{task_id}

📌 Текущие данные:
• Категория: {task['category']}
• Ссылка: {task['link']}
• Всего мест: {task['total_count']}
• Выполнено: {task['done_count']}
• Цена за отзыв: {task['price_per_review']}₽
• Статус: {'Завершено' if task['status'] == 'completed' else 'Активно'}

Выберите что редактировать:
"""
        keyboard = get_edit_task_options_keyboard(task_id)
        await query.edit_message_text(text, reply_markup=keyboard)

    elif data.startswith('task_field_'):
        field = data.split('_')[2]
        task_id = int(data.split('_')[3])

        context.user_data['editing_field'] = field
        context.user_data['editing_task'] = task_id

        field_names = {
            'category': 'категорию',
            'link': 'ссылку',
            'total': 'количество мест',
            'price': 'цену за отзыв',
            'status': 'статус'
        }

        await query.edit_message_text(f"✏️ Введите новое значение для {field_names.get(field, field)}:")
        return TASK_EDIT_VALUE

    elif data.startswith('delete_task_'):
        task_id = int(data.split('_')[2])

        cursor = db.conn.cursor()
        cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
        cursor.execute('DELETE FROM user_tasks WHERE task_id = ?', (task_id,))
        cursor.execute('DELETE FROM reviews WHERE task_id = ?', (task_id,))
        db.conn.commit()

        await query.edit_message_text(f"✅ Задание #{task_id} удалено")
        keyboard = get_back_to_admin_keyboard()
        await query.message.reply_text("Перейти в админ-панель:", reply_markup=keyboard)

    elif data.startswith('check_reviews_'):
        try:
            index = int(data.split('_')[2])
        except:
            index = 0

        total_count = db.get_pending_reviews_count()

        if total_count == 0:
            await query.edit_message_text("✅ Нет отзывов на проверку")
            return

        if index >= total_count:
            index = total_count - 1
        if index < 0:
            index = 0

        review = db.get_pending_review_by_index(index)

        if not review:
            await query.edit_message_text("❌ Отзыв не найден")
            return

        text = f"""
📝 ОТЗЫВ НА ПРОВЕРКУ #{review['review_id']}:

Исполнитель: @{review['username']} ({review['full_name']})
Категория: {review['category']}
Ссылка: {review['link']}
Текст отзыва: {review['text']}

Нажмите "👁️ Посмотреть скриншот" для просмотра
"""

        keyboard = get_review_keyboard(review['review_id'], index, total_count)
        await query.edit_message_text(text, reply_markup=keyboard)

    elif data.startswith('payments_'):
        try:
            index = int(data.split('_')[1])
        except:
            index = 0

        total_count = db.get_pending_payments_count()

        if total_count == 0:
            await query.edit_message_text("✅ Нет заявок на выплату")
            return

        if index >= total_count:
            index = total_count - 1
        if index < 0:
            index = 0

        payment = db.get_pending_payment_by_index(index)

        if not payment:
            await query.edit_message_text("❌ Заявка не найдена")
            return

        crypto_info = ""
        if payment['crypto_type']:
            crypto_info = f"\nКриптовалюта: {payment['crypto_type']}"

        text = f"""
💰 ЗАЯВКА НА ВЫВОД #{payment['payment_id']}:

Исполнитель: @{payment['username']} ({payment['full_name']})
Сумма: {format_balance(payment['amount'])}₽{crypto_info}
Реквизиты: {payment['requisites']}
Дата: {payment['created_at']}
"""

        keyboard = get_payment_keyboard(payment['payment_id'], index, total_count)
        await query.edit_message_text(text, reply_markup=keyboard)

    elif data == 'texts_manage':
        texts = db.get_texts()

        if not texts:
            text = "📝 База текстов пуста\n\nНажмите '📥 Добавить текст' для создания нового"
        else:
            text = f"📚 УПРАВЛЕНИЕ ТЕКСТАМИ\n\nВсего текстов: {len(texts)}\n\nСписок текстов:"

        keyboard = get_texts_keyboard(texts)
        await query.edit_message_text(text, reply_markup=keyboard)

    elif data == 'back_to_admin':
        keyboard = get_admin_keyboard()
        await query.edit_message_text("👑 Админ-панель", reply_markup=keyboard)

    elif data == 'exit_admin':
        user_id = query.from_user.id
        keyboard = get_main_keyboard(user_id, is_admin(user_id))
        await query.edit_message_text("🏠 Возвращаемся в главное меню...", reply_markup=keyboard)


# Обработка нажатия на задание
async def task_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if not query.data.startswith('task_'):
        return

    task_id = int(query.data.split('_')[1])
    task = db.get_task(task_id)

    if not task:
        await query.edit_message_text("❌ Задание не найдено")
        return

    # Проверяем, не брал ли пользователь уже это задание
    cursor = db.conn.cursor()
    cursor.execute('SELECT 1 FROM user_tasks WHERE user_id = ? AND task_id = ?', (user_id, task_id))
    if cursor.fetchone():
        await query.edit_message_text("❌ Вы уже брали это задание")
        return

    # Проверяем, остались ли места
    if task['done_count'] >= task['total_count']:
        await query.edit_message_text("❌ Все места в этом задании уже заняты")
        return

    # Показываем подтверждение взятия задания
    remaining = task['total_count'] - task['done_count']
    text = f"""
🎯 ПОДТВЕРЖДЕНИЕ ВЗЯТИЯ ЗАДАНИЯ:

Категория: {task['category']}
Ссылка: {task['link']}
Осталось мест: {remaining}/{task['total_count']}
Цена за отзыв: {task['price_per_review']}₽

⚠️ Вы уверены, что хотите взять это задание?
После взятия задание будет закреплено за вами на 24 часа.
"""

    keyboard = get_confirm_task_take_keyboard(task_id)
    await query.edit_message_text(text, reply_markup=keyboard)


# Подтверждение взятия задания
async def confirm_task_take_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data.startswith('confirm_take_'):
        task_id = int(query.data.split('_')[2])

        # Добавляем запись, что пользователь взял задание
        success = db.add_user_task(user_id, task_id)

        if not success:
            await query.edit_message_text("❌ Ошибка при взятии задания")
            return

        task = db.get_task(task_id)

        # Получаем случайный текст из базы
        cursor = db.conn.cursor()
        cursor.execute('SELECT content FROM texts ORDER BY RANDOM() LIMIT 1')
        text_result = cursor.fetchone()

        if text_result:
            text = text_result['content']
        else:
            text = "Отличный сервис! Рекомендую всем!"

        # Экранируем текст для MarkdownV2
        escaped_text = escape_markdown(text, version=2)

        instruction = f"""
🎯 ВЫ ВЗЯЛИ ЗАДАНИЕ:

Категория: {task['category']}
Цена: {task['price_per_review']}₽

📌 ИНСТРУКЦИЯ:
1. Перейдите по ссылке и оставьте готовый отзыв
2. Текст менять ЗАПРЕЩЕНО
3. Аккаунт должен быть подписан человеческим именем
4. Скриншот должен показывать, что отзыв уже ОПУБЛИКОВАН

🔗 Ссылка: {task['link']}

📝 Текст для отзыва:
        {text}

📤 Сделайте скриншот, где видно что отзыв УЖЕ ПРОШЁЛ МОДЕРАЦИЮ (не "отправлен на модерацию", а именно опубликован) и отправьте фото сюда.
"""

        context.user_data[f'current_task_{user_id}'] = {'task_id': task_id, 'text': text}

        await query.edit_message_text(instruction, parse_mode='MarkdownV2')

    elif query.data == 'cancel_take':
        await query.edit_message_text("❌ Взятие задания отменено")


# Обработка скриншотов
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if f'current_task_{user_id}' not in context.user_data:
        await update.message.reply_text(
            "❌ Сначала возьмите задание в разделе '📋 Задания'\n\n"
            "1. Нажмите '📋 Задания'\n"
            "2. Выберите задание\n"
            "3. Подтвердите взятие\n"
            "4. Получите инструкцию\n"
            "5. Отправьте скриншот"
        )
        return

    task_data = context.user_data[f'current_task_{user_id}']
    task_id = task_data['task_id']
    text = task_data['text']

    # Получаем file_id самого большого фото
    photo = update.message.photo[-1]
    file_id = photo.file_id

    # Добавляем отзыв на проверку
    review_id = db.add_review(user_id, task_id, text, file_id)

    # Очищаем данные о текущем задании
    del context.user_data[f'current_task_{user_id}']

    await update.message.reply_text(
        "✅ Скриншот принят!\n\n"
        "Статус: ⏳ Ожидает проверки админом\n"
        "Ожидайте уведомления о результате.\n\n"
        "Обычно проверка занимает от 72 до 87 часов."
    )

    # Уведомляем администраторов
    user = db.get_user(user_id)
    username = user['username'] or user['full_name']

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"📨 НОВЫЙ ОТЗЫВ НА ПРОВЕРКУ!\n\n"
                f"ID: {review_id}\n"
                f"От: @{username}\n"
                f"Задание ID: {task_id}"
            )
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")


# Обработка действий с отзывами
async def review_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        return

    data = query.data

    if data.startswith('view_'):
        review_id = int(data.split('_')[1])

        # Получаем file_id скриншота из базы
        cursor = db.conn.cursor()
        cursor.execute('SELECT screenshot_file_id FROM reviews WHERE review_id = ?', (review_id,))
        result = cursor.fetchone()

        if result:
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=result['screenshot_file_id'],
                    caption=f"Скриншот отзыва #{review_id}"
                )
            except Exception as e:
                logger.error(f"Error sending photo: {e}")
                await query.message.reply_text("❌ Ошибка при отправке скриншота")
        else:
            await query.message.reply_text("❌ Скриншот не найден в базе")

    elif data.startswith('approve_'):
        review_id = int(data.split('_')[1])

        # Начисляем админу 15 рублей
        admin_user = db.get_user(user_id)
        if admin_user:
            db.update_user_balance(user_id, 15)
            logger.info(f"Admin {user_id} получил +15₽ за проверку отзыва #{review_id}")

        if db.approve_review(review_id):
            # Получаем информацию об отзыве для уведомления
            cursor = db.conn.cursor()
            cursor.execute('''
                SELECT r.user_id, t.price_per_review, u.username, t.category
                FROM reviews r
                JOIN tasks t ON r.task_id = t.task_id
                JOIN users u ON r.user_id = u.user_id
                WHERE r.review_id = ?
            ''', (review_id,))
            review = cursor.fetchone()

            if review:
                try:
                    await context.bot.send_message(
                        review['user_id'],
                        f"🎉 ОТЗЫВ ОДОБРЕН!\n\n"
                        f"Задание: {review['category']}\n"
                        f"Сумма: +{review['price_per_review']}₽\n"
                        f"Статус: ✅ Одобрено\n\n"
                        f"Можете взять новое задание!"
                    )
                except Exception as e:
                    logger.error(f"Error notifying user: {e}")

            # Показываем следующий отзыв
            total_count = db.get_pending_reviews_count()
            current_index = 0

            # Ищем текущий индекс
            cursor.execute('''
                SELECT r.review_id, row_number
                FROM (
                    SELECT review_id, ROW_NUMBER() OVER (ORDER BY submitted_at) as row_number
                    FROM reviews 
                    WHERE status = 'pending'
                ) r
                WHERE r.review_id = ?
            ''', (review_id,))
            result = cursor.fetchone()
            if result:
                current_index = result['row_number'] - 1

            if total_count > 0:
                if current_index >= total_count:
                    current_index = total_count - 1

                review = db.get_pending_review_by_index(current_index)
                if review:
                    text = f"""
📝 ОТЗЫВ НА ПРОВЕРКУ #{review['review_id']}:

Исполнитель: @{review['username']} ({review['full_name']})
Категория: {review['category']}
Ссылка: {review['link']}
Текст отзыва: {review['text']}

Нажмите "👁️ Посмотреть скриншот" для просмотра
"""
                    keyboard = get_review_keyboard(review['review_id'], current_index, total_count)
                    await query.edit_message_text(text, reply_markup=keyboard)
                else:
                    await query.edit_message_text("✅ Больше нет отзывов на проверку")
            else:
                await query.edit_message_text("✅ Больше нет отзывов на проверку")
        else:
            await query.edit_message_text("❌ Ошибка при одобрении отзыва")

    elif data.startswith('reject_'):
        review_id = int(data.split('_')[1])

        db.reject_review(review_id)

        # Получаем информацию об отзыве для уведомления
        cursor = db.conn.cursor()
        cursor.execute('''
            SELECT r.user_id, u.username
            FROM reviews r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.review_id = ?
        ''', (review_id,))
        review = cursor.fetchone()

        if review:
            try:
                await context.bot.send_message(
                    review['user_id'],
                    "❌ ОТЗЫВ ОТКЛОНЕН\n\n"
                    "Ваш отзыв был отклонен администратором.\n"
                    "Возможные причины:\n"
                    "• Неправильный скриншот\n"
                    "• Отзыв не соответствует тексту\n"
                    "• Нарушение правил\n\n"
                    "Вы можете взять новое задание."
                )
            except Exception as e:
                logger.error(f"Error notifying user: {e}")

        # Показываем следующий отзыв
        total_count = db.get_pending_reviews_count()
        current_index = 0

        # Ищем текущий индекс
        cursor.execute('''
            SELECT r.review_id, row_number
            FROM (
                SELECT review_id, ROW_NUMBER() OVER (ORDER BY submitted_at) as row_number
                FROM reviews 
                WHERE status = 'pending'
            ) r
            WHERE r.review_id = ?
        ''', (review_id,))
        result = cursor.fetchone()
        if result:
            current_index = result['row_number'] - 1

        if total_count > 0:
            if current_index >= total_count:
                current_index = total_count - 1

            review = db.get_pending_review_by_index(current_index)
            if review:
                text = f"""
📝 ОТЗЫВ НА ПРОВЕРКУ #{review['review_id']}:

Исполнитель: @{review['username']} ({review['full_name']})
Категория: {review['category']}
Ссылка: {review['link']}
Текст отзыва: {review['text']}

Нажмите "👁️ Посмотреть скриншот" для просмотра
"""
                keyboard = get_review_keyboard(review['review_id'], current_index, total_count)
                await query.edit_message_text(text, reply_markup=keyboard)
            else:
                await query.edit_message_text("✅ Больше нет отзывов на проверку")
        else:
            await query.edit_message_text("✅ Больше нет отзывов на проверку")


# Обработка действий с выплатами
async def payment_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        return

    data = query.data

    if data.startswith('pay_'):
        payment_id = int(data.split('_')[1])

        db.approve_payment(payment_id)

        # Получаем информацию о выплате для уведомления
        cursor = db.conn.cursor()
        cursor.execute('''
            SELECT p.user_id, p.amount, u.username, p.crypto_type
            FROM payments p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.payment_id = ?
        ''', (payment_id,))
        payment = cursor.fetchone()

        if payment:
            crypto_info = ""
            if payment['crypto_type']:
                crypto_info = f"\nКриптовалюта: {payment['crypto_type']}"

            try:
                await context.bot.send_message(
                    payment['user_id'],
                    f"💸 ВЫПЛАТА ОСУЩЕСТВЛЕНА!\n\n"
                    f"Сумма: {format_balance(payment['amount'])}₽{crypto_info}\n"
                    f"Статус: ✅ Выплачено\n"
                    f"Деньги должны поступить в течение 24 часов\n\n"
                    f"Спасибо за работу! 💰"
                )
            except Exception as e:
                logger.error(f"Error notifying user: {e}")

        # Показываем следующую выплату
        total_count = db.get_pending_payments_count()
        current_index = 0

        # Ищем текущий индекс
        cursor.execute('''
            SELECT p.payment_id, row_number
            FROM (
                SELECT payment_id, ROW_NUMBER() OVER (ORDER BY created_at) as row_number
                FROM payments 
                WHERE status = 'pending'
            ) p
            WHERE p.payment_id = ?
        ''', (payment_id,))
        result = cursor.fetchone()
        if result:
            current_index = result['row_number'] - 1

        if total_count > 0:
            if current_index >= total_count:
                current_index = total_count - 1

            payment = db.get_pending_payment_by_index(current_index)
            if payment:
                crypto_info = ""
                if payment['crypto_type']:
                    crypto_info = f"\nКриптовалюта: {payment['crypto_type']}"

                text = f"""
💰 ЗАЯВКА НА ВЫВОД #{payment['payment_id']}:

Исполнитель: @{payment['username']} ({payment['full_name']})
Сумма: {format_balance(payment['amount'])}₽{crypto_info}
Реквизиты: {payment['requisites']}
Дата: {payment['created_at']}
"""
                keyboard = get_payment_keyboard(payment['payment_id'], current_index, total_count)
                await query.edit_message_text(text, reply_markup=keyboard)
            else:
                await query.edit_message_text("✅ Больше нет заявок на выплату")
        else:
            await query.edit_message_text("✅ Больше нет заявок на выплату")

    elif data.startswith('decline_pay_'):
        payment_id = int(data.split('_')[2])

        # Отклоняем выплату и возвращаем деньги на баланс
        cursor = db.conn.cursor()
        cursor.execute('SELECT user_id, amount FROM payments WHERE payment_id = ?', (payment_id,))
        payment = cursor.fetchone()

        if payment:
            # Возвращаем деньги на баланс
            cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                           (payment['amount'], payment['user_id']))

            # Обновляем статус выплаты
            cursor.execute('UPDATE payments SET status = "rejected" WHERE payment_id = ?', (payment_id,))
            db.conn.commit()

            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    payment['user_id'],
                    f"❌ ВЫПЛАТА ОТКЛОНЕНА\n\n"
                    f"Ваша заявка на вывод {format_balance(payment['amount'])}₽ была отклонена.\n"
                    f"Деньги возвращены на ваш баланс.\n\n"
                    f"Для уточнения причин обратитесь к администратору."
                )
            except Exception as e:
                logger.error(f"Error notifying user: {e}")

        # Показываем следующую выплату
        total_count = db.get_pending_payments_count()
        current_index = 0

        # Ищем текущий индекс
        cursor.execute('''
            SELECT p.payment_id, row_number
            FROM (
                SELECT payment_id, ROW_NUMBER() OVER (ORDER BY created_at) as row_number
                FROM payments 
                WHERE status = 'pending'
            ) p
            WHERE p.payment_id = ?
        ''', (payment_id,))
        result = cursor.fetchone()
        if result:
            current_index = result['row_number'] - 1

        if total_count > 0:
            if current_index >= total_count:
                current_index = total_count - 1

            payment = db.get_pending_payment_by_index(current_index)
            if payment:
                crypto_info = ""
                if payment['crypto_type']:
                    crypto_info = f"\nКриптовалюта: {payment['crypto_type']}"

                text = f"""
💰 ЗАЯВКА НА ВЫВОД #{payment['payment_id']}:

Исполнитель: @{payment['username']} ({payment['full_name']})
Сумма: {format_balance(payment['amount'])}₽{crypto_info}
Реквизиты: {payment['requisites']}
Дата: {payment['created_at']}
"""
                keyboard = get_payment_keyboard(payment['payment_id'], current_index, total_count)
                await query.edit_message_text(text, reply_markup=keyboard)
            else:
                await query.edit_message_text("✅ Больше нет заявок на выплату")
        else:
            await query.edit_message_text("✅ Больше нет заявок на выплату")


# Обработка действий с текстами
async def texts_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        return

    data = query.data

    if data == 'add_text':
        await query.edit_message_text("📝 Введите новый текст для базы:")
        return ADD_TEXT

    elif data.startswith('text_'):
        text_id = int(data.split('_')[1])

        cursor = db.conn.cursor()
        cursor.execute('SELECT * FROM texts WHERE text_id = ?', (text_id,))
        text = cursor.fetchone()

        if text:
            message = f"📝 Текст #{text_id}\n\n{text['content']}\n\nИспользован: {text['used_count']} раз"
            keyboard = get_text_action_keyboard(text_id)
            await query.edit_message_text(message, reply_markup=keyboard)

    elif data.startswith('delete_text_'):
        text_id = int(data.split('_')[2])

        db.delete_text(text_id)

        texts = db.get_texts()
        keyboard = get_texts_keyboard(texts)
        await query.edit_message_text("✅ Текст удален", reply_markup=keyboard)

    elif data == 'texts_manage':
        texts = db.get_texts()
        keyboard = get_texts_keyboard(texts)
        await query.edit_message_text("📚 База текстов", reply_markup=keyboard)


# Обработка добавления текста
async def add_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_content = update.message.text.strip()

    if not text_content:
        await update.message.reply_text("❌ Текст не может быть пустым. Введите текст:")
        return ADD_TEXT

    text_id = db.add_text(text_content)

    texts = db.get_texts()
    keyboard = get_texts_keyboard(texts)

    await update.message.reply_text(f"✅ Текст добавлен (ID: {text_id})", reply_markup=keyboard)

    return ConversationHandler.END


# Обработка сообщений от админа при создании задания
async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text.strip()

    # Проверяем, является ли пользователь админом
    if not is_admin(user_id):
        return

    # Проверяем, находится ли админ в процессе создания задания
    if 'admin_task' not in context.user_data:
        return

    task_data = context.user_data['admin_task']
    step = task_data.get('step')

    if step == 'link':
        # Проверяем, что ссылка валидная
        if not message_text.startswith(('http://', 'https://')):
            await update.message.reply_text(
                "❌ Ссылка должна начинаться с http:// или https://\nПожалуйста, введите правильную ссылку:")
            return

        # Сохраняем ссылку
        context.user_data['admin_task']['link'] = message_text
        context.user_data['admin_task']['step'] = 'count'

        await update.message.reply_text("📌 Введите количество отзывов (число):")

    elif step == 'count':
        try:
            count = int(message_text)
            if count <= 0:
                await update.message.reply_text("❌ Количество должно быть больше 0. Введите число:")
                return

            if count > 1000:
                await update.message.reply_text("❌ Слишком большое количество. Введите число до 1000:")
                return

            context.user_data['admin_task']['count'] = count

            task = context.user_data['admin_task']

            confirm_text = f"""
📋 ПОДТВЕРЖДЕНИЕ ЗАДАНИЯ:

Категория: {task['category']}
Ссылка: {task['link']}
Количество отзывов: {task['count']}
Цена за отзыв: {task['price']}₽
Общая стоимость: {task['count'] * task['price']}₽

✅ Создать задание?
"""

            keyboard = get_confirm_keyboard()
            await update.message.reply_text(confirm_text, reply_markup=keyboard)

        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число:")


# Подтверждение создания задания
async def confirm_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'confirm_task':
        task = context.user_data['admin_task']

        task_id = db.add_task(
            category=task['category'],
            link=task['link'],
            total_count=task['count'],
            price_per_review=task['price']
        )

        # Добавляем тексты к заданию
        cursor = db.conn.cursor()
        cursor.execute('SELECT text_id FROM texts')
        texts = cursor.fetchall()

        for text in texts:
            cursor.execute('INSERT OR IGNORE INTO task_texts (task_id, text_id) VALUES (?, ?)',
                           (task_id, text['text_id']))

        db.conn.commit()

        await query.edit_message_text(
            f"✅ ЗАДАНИЕ СОЗДАНО!\n\n"
            f"ID: {task_id}\n"
            f"Категория: {task['category']}\n"
            f"Количество: {task['count']}\n"
            f"Цена за отзыв: {task['price']}₽\n"
            f"Общая стоимость: {task['count'] * task['price']}₽\n\n"
            f"Задание доступно исполнителям в разделе '📋 Задания'"
        )

        # Очищаем данные
        if 'admin_task' in context.user_data:
            del context.user_data['admin_task']

    elif query.data == 'cancel_task':
        await query.edit_message_text("❌ Создание задания отменено")

        if 'admin_task' in context.user_data:
            del context.user_data['admin_task']

    keyboard = get_back_to_admin_keyboard()
    await query.message.reply_text("Перейти в админ-панель:", reply_markup=keyboard)


# Отмена диалога (кнопка отмены)
async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'cancel':
        # Очищаем данные админа, если есть
        if 'admin_task' in context.user_data:
            del context.user_data['admin_task']

        keyboard = get_admin_keyboard()
        await query.edit_message_text("👑 Админ-панель", reply_markup=keyboard)


# Обработка текстовых сообщений (кнопки главного меню)
async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # Регистрируем пользователя при любом действии
    register_user_if_needed(update)

    if text == '📋 Задания':
        await tasks_command(update, context)
    elif text == '👤 Профиль':
        await profile_command(update, context)
    elif text == '💰 Вывод средств':
        await withdraw_command(update, context)
    elif text == '💎 Крипто-вывод':
        await update.message.reply_text(
            f"💎 Для вывода через криптовалюту (TON) используйте кнопку '💰 Вывод средств' и выберите 'Криптовалюту'\n\n"
            f"Укажите сумму вывода и адрес вашего TON кошелька."
        )
    elif text == '👥 Рефералы':
        await referral_command(update, context)
    elif text == '📞 Поддержка':
        await update.message.reply_text(
            f"📞 По всем вопросам обращайтесь к {SUPPORT_USERNAME}\n\n"
            f"Мы всегда готовы помочь!"
        )
    elif text == '📰 Новости':
        await update.message.reply_text(
            f"📰 Новости и обновления в нашем канале: {NEWS_CHANNEL}\n\n"
            f"Подписывайтесь, чтобы быть в курсе всех новостей!"
        )
    elif text == '⚙️ Админ-панель':
        if is_admin(user_id):
            await admin_command(update, context)
        else:
            await update.message.reply_text("⛔ У вас нет доступа к админ-панели")
    elif text == '🏠 Выход':
        await exit_command(update, context)


# Отмена любого диалога
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Очищаем данные о текущем задании, если есть
    if f'current_task_{user_id}' in context.user_data:
        del context.user_data[f'current_task_{user_id}']

    # Очищаем данные админа, если есть
    if 'admin_task' in context.user_data:
        del context.user_data['admin_task']

    # Очищаем данные о выводе
    if 'withdraw_user_id' in context.user_data:
        context.user_data.clear()

    keyboard = get_main_keyboard(user_id, is_admin(user_id))
    await update.message.reply_text("❌ Действие отменено", reply_markup=keyboard)

    return ConversationHandler.END


# Обработка редактирования задания
async def task_edit_value_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет доступа")
        return ConversationHandler.END

    new_value = update.message.text.strip()
    field = context.user_data.get('editing_field')
    task_id = context.user_data.get('editing_task')

    if not field or not task_id:
        await update.message.reply_text("❌ Ошибка: данные не найдены")
        return ConversationHandler.END

    cursor = db.conn.cursor()

    try:
        if field == 'category':
            cursor.execute('UPDATE tasks SET category = ? WHERE task_id = ?', (new_value, task_id))
        elif field == 'link':
            cursor.execute('UPDATE tasks SET link = ? WHERE task_id = ?', (new_value, task_id))
        elif field == 'total':
            new_count = int(new_value)
            cursor.execute('UPDATE tasks SET total_count = ? WHERE task_id = ?', (new_count, task_id))
        elif field == 'price':
            new_price = float(new_value)
            cursor.execute('UPDATE tasks SET price_per_review = ? WHERE task_id = ?', (new_price, task_id))
        elif field == 'status':
            cursor.execute('UPDATE tasks SET status = ? WHERE task_id = ?', (new_value, task_id))

        db.conn.commit()
        await update.message.reply_text(f"✅ Поле '{field}' обновлено")

        # Показываем обновленные данные задания
        task = db.get_task(task_id)
        text = f"""
✏️ ЗАДАНИЕ #{task_id} ОБНОВЛЕНО

📌 Текущие данные:
• Категория: {task['category']}
• Ссылка: {task['link']}
• Всего мест: {task['total_count']}
• Выполнено: {task['done_count']}
• Цена за отзыв: {task['price_per_review']}₽
• Статус: {'Завершено' if task['status'] == 'completed' else 'Активно'}
"""
        keyboard = get_back_to_admin_keyboard()
        await update.message.reply_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error updating task: {e}")
        await update.message.reply_text(f"❌ Ошибка при обновлении: {e}")

    # Очищаем данные
    if 'editing_field' in context.user_data:
        del context.user_data['editing_field']
    if 'editing_task' in context.user_data:
        del context.user_data['editing_task']

    return ConversationHandler.END


# Обработка неизвестных команд
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Регистрируем пользователя
    register_user_if_needed(update)

    user_id = update.effective_user.id
    keyboard = get_main_keyboard(user_id, is_admin(user_id))

    await update.message.reply_text(
        "❓ Неизвестная команда\n\n"
        "Используйте кнопки меню или команды:\n"
        "/start - Начать работу с ботом\n"
        "/admin - Админ-панель (только для администраторов)\n"
        "/tasks - Просмотр заданий\n"
        "/profile - Ваш профиль\n"
        "/referral - Реферальная система\n"
        "/cancel - Отмена текущего действия\n\n"
        "Или используйте кнопки ниже:",
        reply_markup=keyboard
    )


