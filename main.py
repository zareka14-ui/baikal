import asyncio
import logging
import os
import sys
import re
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
PORT = int(os.getenv("PORT", 8080))

# Платёжные реквизиты
PAYMENT_LINK = "https://sberbank.com/sms/pbpn?requisiteNumber=79124591439"

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# --- МАШИНА СОСТОЯНИЙ ---
class Registration(StatesGroup):
    name = State()
    phone = State()
    confirm = State()
    payment = State()

# --- ВАЛИДАЦИЯ ТЕЛЕФОНА ---
def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Проверяет номер телефона.
    Возвращает (валиден_ли, очищенный_номер)
    """
    # Удаляем все пробелы, скобки, дефисы
    clean_phone = re.sub(r'[\s\(\)\-+]', '', phone)
    
    # Проверяем, что остались только цифры
    if not clean_phone.isdigit():
        return False, ""
    
    # Проверяем длину (10-15 цифр для международных номеров)
    if len(clean_phone) < 10 or len(clean_phone) > 15:
        return False, ""
    
    # Для российских номеров проверяем начало
    if clean_phone.startswith('7') or clean_phone.startswith('8'):
        if len(clean_phone) != 11:
            return False, ""
        # Приводим к формату +7XXXXXXXXXX
        if clean_phone.startswith('8'):
            clean_phone = '7' + clean_phone[1:]
        return True, f"+7{clean_phone[1:]}"
    elif clean_phone.startswith('9') and len(clean_phone) == 10:
        # Номер без кода страны
        return True, f"+7{clean_phone}"
    else:
        # Другие страны
        return True, f"+{clean_phone}"

# --- КЛАВИАТУРЫ ---
def main_kb():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🌊 Записаться на тур")]],
        resize_keyboard=True
    )

def cancel_kb():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

# --- ТЕКСТЫ ---
TOUR_INFO = """🌊 *ТУР НА БАЙКАЛ 25.02-03.03*

💰 *Стоимость:* 79 000 ₽
💵 *Депозит:* 20 000 ₽

✅ *Включено:*
• Проживание
• Завтраки и ужины
• Экскурсии и активности
• Фото/видео с дрона

❌ *Дополнительно:*
• Перелёт
• Обеды, музеи
• Личные расходы"""

# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        f"Привет! {TOUR_INFO}\n\n"
        "Нажмите кнопку ниже для записи:",
        parse_mode="Markdown",
        reply_markup=main_kb()
    )

@dp.message(F.text == "🌊 Записаться на тур")
async def start_registration(message: types.Message, state: FSMContext):
    await message.answer(
        "📝 *Шаг 1/3*\nВведите ваше ФИО полностью:",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    await state.set_state(Registration.name)

@dp.message(F.text == "❌ Отмена")
async def cancel_all(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Регистрация отменена", reply_markup=main_kb())

@dp.message(Registration.name, F.text)
async def get_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_all(message, state)
        return
    
    await state.update_data(name=message.text)
    await message.answer(
        "📱 *Шаг 2/3*\nВведите номер телефона:\n\n"
        "Примеры:\n"
        "• 79123456789\n"
        "• +79123456789\n"
        "• 8 (912) 345-67-89",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    await state.set_state(Registration.phone)

@dp.message(Registration.phone, F.text)
async def get_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_all(message, state)
        return
    
    # Валидация телефона
    is_valid, clean_phone = validate_phone(message.text)
    
    if not is_valid:
        await message.answer(
            "❌ *Некорректный номер телефона*\n\n"
            "Пожалуйста, введите номер в одном из форматов:\n"
            "• 79123456789 (11 цифр)\n"
            "• 9123456789 (10 цифр)\n"
            "• +7 912 345 67 89\n\n"
            "Введите номер заново:",
            parse_mode="Markdown",
            reply_markup=cancel_kb()
        )
        return
    
    await state.update_data(phone=clean_phone)
    data = await state.get_data()
    
    text = (
        "✅ *Шаг 3/3*\n"
        "Проверьте данные:\n\n"
        f"👤 *ФИО:* {data['name']}\n"
        f"📞 *Телефон:* {clean_phone}\n"
        f"💵 *Депозит:* 20 000 ₽\n\n"
        "Всё верно?"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Да", callback_data="confirm"),
            types.InlineKeyboardButton(text="✏️ Нет", callback_data="restart")
        ]
    ])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)
    await state.set_state(Registration.confirm)

@dp.callback_query(F.data == "restart")
async def restart(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_registration(callback.message, state)

@dp.callback_query(F.data == "confirm", Registration.confirm)
async def confirm_data(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    payment_text = (
        "💳 *ОПЛАТА ДЕПОЗИТА*\n\n"
        "Для бронирования оплатите 20 000 ₽\n\n"
        f"📲 *Ссылка для оплаты:*\n{PAYMENT_LINK}\n\n"
        "Или по номеру: `+79124591439`\n"
        "Получатель: Екатерина Б.\n\n"
        "*После оплаты отправьте скриншот чека*"
    )
    
    await callback.message.edit_text(payment_text, parse_mode="Markdown")
    await state.set_state(Registration.payment)

@dp.message(Registration.payment)
async def get_payment(message: types.Message, state: FSMContext):
    # Проверяем, есть ли фото или документ
    if not (message.photo or message.document):
        await message.answer("Пожалуйста, отправьте скриншот чека (фото или документ)")
        return
    
    # Получаем данные пользователя
    data = await state.get_data()
    user = message.from_user
    
    # Формируем детальную информацию о пользователе
    user_id = user.id
    username = f"@{user.username}" if user.username else "не указан"
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    
    # Формируем сообщение админу
    admin_msg = (
        "🔥 *НОВАЯ ЗАЯВКА НА ТУР НА БАЙКАЛ!*\n\n"
        "📋 *ДАННЫЕ ЗАЯВКИ:*\n"
        f"👤 *ФИО:* {data['name']}\n"
        f"📞 *Телефон:* {data['phone']}\n"
        f"💵 *Сумма тура:* 79 000 ₽\n"
        f"💰 *Депозит:* 20 000 ₽\n\n"
        
        "👤 *ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:*\n"
        f"🆔 *Telegram ID:* `{user_id}`\n"
        f"👤 *Username:* {username}\n"
    )
    
    if full_name:
        admin_msg += f"👤 *Имя в Telegram:* {full_name}\n"
    
    admin_msg += (
        f"📅 *Дата заявки:* {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"📎 *Тип сообщения:* {'Фото' if message.photo else 'Документ'}"
    )
    
    # Отправляем админу
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
            
            # Отправляем фото или документ
            if message.photo:
                await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, 
                                   caption=f"Чек от пользователя: {data['name']}")
            elif message.document:
                await bot.send_document(ADMIN_ID, message.document.file_id,
                                      caption=f"Чек от пользователя: {data['name']}")
            
            logger.info(f"Заявка отправлена администратору от {data['name']} (ID: {user_id})")
            
        except Exception as e:
            logger.error(f"Ошибка отправки админу: {e}")
            # Сохраняем ошибку в лог
            try:
                error_msg = f"❌ Ошибка при отправке админу: {str(e)}"
                await bot.send_message(ADMIN_ID, error_msg[:4000])
            except:
                pass
    
    # Подтверждение пользователю
    await message.answer(
        "✅ *ЗАЯВКА ПРИНЯТА!*\n\n"
        "Благодарим вас за доверие! Мы свяжемся с вами. И добавим в закрытый чат группы.\n\n"
        ,
        reply_markup=main_kb()
    )
    
    await state.clear()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def health_check(request):
    return web.Response(text="Bot is alive")

async def start_web():
    """Запуск веб-сервера для keep-alive"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")
    
    # Возвращаем runner для корректного завершения
    return runner

# --- ЗАПУСК ---
async def main():
    logger.info("Starting bot...")
    
    try:
        # Запускаем веб-сервер
        web_runner = await start_web()
        
        # Настраиваем бота
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Информация о запуске
        bot_info = await bot.get_me()
        logger.info(f"Bot @{bot_info.username} started successfully")
        
        if ADMIN_ID:
            try:
                await bot.send_message(ADMIN_ID, "🤖 Бот запущен и готов к работе!")
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение администратору: {e}")
        
        # Запускаем поллинг
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise
    finally:
        # При завершении работы
        logger.info("Bot stopped")

if __name__ == "__main__":
    # Для Render важно обрабатывать KeyboardInterrupt
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed with error: {e}")
