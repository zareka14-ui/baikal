import asyncio
import logging
import os
import sys
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

# Для Render бесплатного тарифа
OFFER_LINK = "https://disk.yandex.ru/i/ваша_оферта"
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
        "📱 *Шаг 2/3*\nВведите номер телефона (+7...):",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    await state.set_state(Registration.phone)

@dp.message(Registration.phone, F.text)
async def get_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_all(message, state)
        return
    
    await state.update_data(phone=message.text)
    data = await state.get_data()
    
    text = (
        "✅ *Шаг 3/3*\n"
        "Проверьте данные:\n"
        f"👤 *ФИО:* {data['name']}\n"
        f"📞 *Телефон:* {data['phone']}\n"
        f"💵 *Депозит:* 20 000 ₽\n\n"
        "Всё верно?"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Да, продолжить", callback_data="confirm")],
        [types.InlineKeyboardButton(text="✏️ Исправить", callback_data="restart")],
        [types.InlineKeyboardButton(text="📄 Оферта", url=OFFER_LINK)]
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
    
    # Получаем данные
    data = await state.get_data()
    user = message.from_user
    
    # Формируем сообщение админу
    admin_msg = (
        "🔥 *НОВАЯ ЗАЯВКА НА БАЙКАЛ!*\n\n"
        f"👤 *ФИО:* {data['name']}\n"
        f"📞 *Телефон:* {data['phone']}\n"
        f"🆔 *ID:* {user.id}\n"
        f"👤 *Username:* @{user.username if user.username else 'нет'}\n"
        f"📅 *Время:* {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"💵 *Сумма:* 79 000 ₽\n"
        f"💰 *Депозит:* 20 000 ₽"
    )
    
    # Отправляем админу
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
            if message.photo:
                await bot.send_photo(ADMIN_ID, message.photo[-1].file_id)
            elif message.document:
                await bot.send_document(ADMIN_ID, message.document.file_id)
        except Exception as e:
            logger.error(f"Ошибка отправки админу: {e}")
    
    # Подтверждение пользователю
    await message.answer(
        "✅ *ЗАЯВКА ПРИНЯТА!*\n\n"
        "Спасибо за бронирование! Мы свяжемся с вами в ближайшее время для уточнения деталей.\n\n"
        "По вопросам: @ваш_менеджер",
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
    return runner

# --- ЗАПУСК ---
async def main():
    logger.info("Starting bot...")
    
    # Запускаем веб-сервер и бота параллельно
    web_runner = await start_web()
    
    # Настраиваем бота
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем поллинг
    await dp.start_polling(bot)
    
    # Очистка при остановке
    await web_runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
