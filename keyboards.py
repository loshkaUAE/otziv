from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard(user_id, is_admin):
    if is_admin:
        keyboard = [
            ['📋 Задания', '👤 Профиль'],
            ['💰 Вывод средств', '💎 Крипто-вывод'],
            ['👥 Рефералы', '📞 Поддержка'],
            ['📰 Новости', '⚙️ Админ-панель'],
            ['🏠 Выход']
        ]
    else:
        keyboard = [
            ['📋 Задания', '👤 Профиль'],
            ['💰 Вывод средств', '💎 Крипто-вывод'],
            ['👥 Рефералы', '📞 Поддержка'],
            ['📰 Новости', '🏠 Выход']
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Добавить задание", callback_data='add_task')],
        [InlineKeyboardButton("✏️ Редактировать задание", callback_data='edit_tasks')],
        [InlineKeyboardButton("📊 Статистика", callback_data='statistics')],
        [InlineKeyboardButton("🏆 Топы", callback_data='top_stats')],
        [InlineKeyboardButton("✅ Проверка отзывов", callback_data='check_reviews_0')],
        [InlineKeyboardButton("💰 Выплаты", callback_data='payments_0')],
        [InlineKeyboardButton("📝 База текстов", callback_data='texts_manage')],
        [InlineKeyboardButton("🏠 В главное меню", callback_data='exit_admin')]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_tasks_keyboard(tasks):
    keyboard = []
    for task in tasks:
        remaining = task['total_count'] - task['done_count']
        keyboard.append([
            InlineKeyboardButton(
                f"{task['category']} - {remaining}/{task['total_count']} мест - {task['price_per_review']}₽",
                callback_data=f'task_{task["task_id"]}'
            )
        ])
    return InlineKeyboardMarkup(keyboard)


def get_category_keyboard():
    keyboard = [
        [InlineKeyboardButton("Яндекс Карты", callback_data='cat_yandex')],
        [InlineKeyboardButton("2ГИС", callback_data='cat_2gis')],
        [InlineKeyboardButton("Другое", callback_data='cat_other')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel')]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_review_keyboard(review_id, current_index, total_count):
    keyboard = []

    # Кнопка просмотра скриншота
    keyboard.append([
        InlineKeyboardButton("👁️ Посмотреть скриншот", callback_data=f'view_{review_id}')
    ])

    # Кнопки одобрения/отклонения
    keyboard.append([
        InlineKeyboardButton("✅ Одобрить (+15₽ админу)", callback_data=f'approve_{review_id}'),
        InlineKeyboardButton("❌ Отклонить", callback_data=f'reject_{review_id}')
    ])

    # Кнопки навигации
    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f'check_reviews_{current_index - 1}'))

    nav_buttons.append(InlineKeyboardButton(f"{current_index + 1}/{total_count}", callback_data='noop'))

    if current_index < total_count - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data=f'check_reviews_{current_index + 1}'))

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Кнопка выхода
    keyboard.append([InlineKeyboardButton("🏠 Выход", callback_data='back_to_admin')])

    return InlineKeyboardMarkup(keyboard)


def get_payment_keyboard(payment_id, current_index, total_count):
    keyboard = []

    # Кнопки выплаты
    keyboard.append([
        InlineKeyboardButton("✅ Выплатить", callback_data=f'pay_{payment_id}'),
        InlineKeyboardButton("❌ Отклонить", callback_data=f'decline_pay_{payment_id}')
    ])

    # Кнопки навигации
    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f'payments_{current_index - 1}'))

    nav_buttons.append(InlineKeyboardButton(f"{current_index + 1}/{total_count}", callback_data='noop'))

    if current_index < total_count - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data=f'payments_{current_index + 1}'))

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Кнопка выхода
    keyboard.append([InlineKeyboardButton("🏠 Выход", callback_data='back_to_admin')])

    return InlineKeyboardMarkup(keyboard)


def get_withdraw_type_keyboard():
    keyboard = [
        [InlineKeyboardButton("💳 Банковская карта", callback_data='withdraw_card')],
        [InlineKeyboardButton("💎 Криптовалюта (TON)", callback_data='withdraw_crypto')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel')]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_texts_keyboard(texts):
    keyboard = []
    for i, text in enumerate(texts, 1):
        text_preview = text['content'][:50] + '...' if len(text['content']) > 50 else text['content']
        keyboard.append([
            InlineKeyboardButton(f"{i}. {text_preview}", callback_data=f'text_{text["text_id"]}')
        ])
    keyboard.append([
        InlineKeyboardButton("📥 Добавить текст", callback_data='add_text'),
        InlineKeyboardButton("🏠 Выход", callback_data='back_to_admin')
    ])
    return InlineKeyboardMarkup(keyboard)


def get_text_action_keyboard(text_id):
    keyboard = [
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data=f'edit_text_{text_id}'),
            InlineKeyboardButton("🗑️ Удалить", callback_data=f'delete_text_{text_id}')
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data='texts_manage'),
            InlineKeyboardButton("🏠 Выход", callback_data='back_to_admin')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data='confirm_task'),
            InlineKeyboardButton("❌ Отмена", callback_data='cancel_task')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("◀️ В админ-панель", callback_data='back_to_admin')]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_task_take_keyboard(task_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Взять задание", callback_data=f'confirm_take_{task_id}'),
            InlineKeyboardButton("❌ Отмена", callback_data='cancel_take')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_edit_tasks_keyboard(tasks):
    keyboard = []
    for task in tasks:
        keyboard.append([
            InlineKeyboardButton(f"✏️ Задание #{task['task_id']}", callback_data=f'edit_task_{task["task_id"]}')
        ])
    keyboard.append([
        InlineKeyboardButton("◀️ Назад", callback_data='back_to_admin'),
        InlineKeyboardButton("🏠 Выход", callback_data='exit_admin')
    ])
    return InlineKeyboardMarkup(keyboard)


def get_edit_task_options_keyboard(task_id):
    keyboard = [
        [InlineKeyboardButton("📌 Категория", callback_data=f'task_field_category_{task_id}')],
        [InlineKeyboardButton("🔗 Ссылка", callback_data=f'task_field_link_{task_id}')],
        [InlineKeyboardButton("🔢 Количество мест", callback_data=f'task_field_total_{task_id}')],
        [InlineKeyboardButton("💰 Цена", callback_data=f'task_field_price_{task_id}')],
        [InlineKeyboardButton("📊 Статус", callback_data=f'task_field_status_{task_id}')],
        [InlineKeyboardButton("🗑️ Удалить задание", callback_data=f'delete_task_{task_id}')],
        [InlineKeyboardButton("◀️ Назад к списку", callback_data='edit_tasks'),
         InlineKeyboardButton("🏠 Выход", callback_data='back_to_admin')]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_exit_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏠 В главное меню", callback_data='exit_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)
