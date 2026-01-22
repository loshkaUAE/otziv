
# !/usr/bin/env python3
"""
Главный файл Telegram бота для заработка на отзывах
Полностью рабочий код с поддержкой .env файла
"""

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler

# Импорт конфигурации
from config import BOT_TOKEN, ADMIN_IDS, check_config

# Импорт функций из handlers
from handlers import (
    # Основные команды
    start_command, admin_command, tasks_command, profile_command, referral_command,
    exit_command, cancel_handler,

    # Функции вывода средств
    withdraw_command, withdraw_type_handler, withdraw_amount_handler,
    withdraw_requisites_handler, crypto_address_handler,

    # Обработчики сообщений
    text_message_handler, admin_message_handler, photo_handler, unknown_command,

    # Callback обработчики
    admin_callback_handler, task_callback_handler, confirm_task_take_callback,
    review_action_handler, payment_action_handler, texts_action_handler,
    confirm_task_callback, cancel_callback,

    # Обработчики текстов и заданий
    add_text_handler, task_edit_value_handler,

    # Состояния
    WITHDRAW_TYPE, WITHDRAW_AMOUNT, WITHDRAW_REQUISITES, CRYPTO_ADDRESS,
    ADD_TEXT, TASK_EDIT_VALUE
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция запуска бота"""

    # ПРОВЕРКА КОНФИГУРАЦИИ
    print("=" * 50)
    print("🔧 ИНИЦИАЛИЗАЦИЯ БОТА")
    print("=" * 50)

    try:
        check_config()
    except ValueError as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("🛑 Бот не может быть запущен.")
        return

    if not BOT_TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не найден!")
        print("📋 Создайте файл .env в папке проекта со строкой:")
        print("   BOT_TOKEN=ваш_токен_от_BotFather")
        return

    print("✅ Конфигурация проверена успешно!")
    print(f"📊 Администраторов: {len(ADMIN_IDS)}")
    print("-" * 50)

    # СОЗДАНИЕ ПРИЛОЖЕНИЯ
    print("🤖 Создание приложения Telegram бота...")
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        print("✅ Приложение создано успешно!")
    except Exception as e:
        print(f"❌ ОШИБКА при создании приложения: {e}")
        print("   Проверьте правильность BOT_TOKEN в .env файле")
        return

    # ===== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ КОМАНД =====
    print("📝 Регистрация обработчиков команд...")

    # Основные команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("tasks", tasks_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(CommandHandler("cancel", cancel_handler))
    application.add_handler(CommandHandler("exit", exit_command))

    # Обработчик вывода средств
    print("💳 Настройка обработчика вывода средств...")
    withdraw_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^💰 Вывод средств$'), withdraw_command)],
        states={
            WITHDRAW_TYPE: [
                CallbackQueryHandler(withdraw_type_handler, pattern='^(withdraw_card|withdraw_crypto|cancel)$')],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount_handler)],
            WITHDRAW_REQUISITES: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_requisites_handler)],
            CRYPTO_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, crypto_address_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel_handler), CommandHandler("exit", exit_command)]
    )
    application.add_handler(withdraw_conv)

    # Обработчик добавления текста
    print("📝 Настройка обработчика текстов...")
    add_text_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(texts_action_handler, pattern='^add_text$')],
        states={
            ADD_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_text_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel_handler), CommandHandler("exit", exit_command)]
    )
    application.add_handler(add_text_conv)

    # Обработчик редактирования заданий
    print("✏️ Настройка обработчика редактирования заданий...")
    task_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback_handler, pattern='^task_field_')],
        states={
            TASK_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_edit_value_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel_handler), CommandHandler("exit", exit_command)]
    )
    application.add_handler(task_edit_conv)

    # ===== РЕГИСТРАЦИЯ CALLBACK ОБРАБОТЧИКОВ =====
    print("🔘 Регистрация callback обработчиков...")

    # Админ-панель
    application.add_handler(CallbackQueryHandler(admin_callback_handler,
                                                 pattern='^(add_task|statistics|texts_manage|back_to_admin|edit_tasks|top_stats|exit_admin)$'))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^cat_'))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^check_reviews_'))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^payments_'))

    # Редактирование заданий
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^edit_task_'))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^delete_task_'))

    # Задания
    application.add_handler(CallbackQueryHandler(task_callback_handler, pattern='^task_'))
    application.add_handler(CallbackQueryHandler(confirm_task_take_callback, pattern='^(confirm_take_|cancel_take)$'))

    # Отзывы
    application.add_handler(CallbackQueryHandler(review_action_handler, pattern='^(view_|approve_|reject_)'))

    # Выплаты
    application.add_handler(CallbackQueryHandler(payment_action_handler, pattern='^(pay_|decline_pay_)'))

    # Тексты
    application.add_handler(
        CallbackQueryHandler(texts_action_handler, pattern='^(text_|delete_text_|edit_text_|texts_manage)$'))

    # Подтверждение задач
    application.add_handler(CallbackQueryHandler(confirm_task_callback, pattern='^(confirm_task|cancel_task)$'))

    # Отмена и выход
    application.add_handler(CallbackQueryHandler(cancel_callback, pattern='^cancel$'))

    # ===== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ СООБЩЕНИЙ =====
    print("💬 Регистрация обработчиков сообщений...")

    # 1. Кнопки главного меню
    application.add_handler(
        MessageHandler(filters.Regex(
            '^(📋 Задания|👤 Профиль|💰 Вывод средств|💎 Крипто-вывод|👥 Рефералы|📞 Поддержка|📰 Новости|⚙️ Админ-панель|🏠 Выход)$'),
            text_message_handler))

    # 2. Обработчик сообщений админа (для создания заданий)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message_handler))

    # 3. Обработчик фото (скриншоты)
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    # 4. Обработчик неизвестных команд
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_command))

    # ===== ЗАПУСК БОТА =====
    print("-" * 50)
    print("🚀 ЗАПУСК БОТА...")
    print("=" * 50)

    try:
        # Выводим информацию для отладки
        print(f"✅ Бот успешно инициализирован!")
        print(f"   Токен: {'✓' if BOT_TOKEN else '✗'}")
        print(f"   Администраторы: {ADMIN_IDS}")
        print(f"   Всего обработчиков: {len(application.handlers)}")
        print("\n📢 Бот запущен и ожидает сообщений...")
        print("   Для остановки нажмите Ctrl+C")
        print("=" * 50)

        # Запускаем бота
        application.run_polling()

    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ: {e}")
        print("🔧 Возможные причины:")
        print("   1. Неправильный BOT_TOKEN в .env файле")
        print("   2. Проблемы с интернет-соединением")
        print("   3. Бот заблокирован в Telegram")
        return


if __name__ == '__main__':
    main()