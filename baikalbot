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
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
)

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
PORT = int(os.getenv("PORT", 8080))
OFFER_LINK = "https://disk.yandex.ru/i/ваша_оферта"  # Замените на реальную ссылку
PAYMENT_LINK = "https://sberbank.com/sms/pbpn?requisiteNumber=79124591439"

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- МАШИНА СОСТОЯНИЙ ---
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    confirm_data = State()
    waiting_for_payment_proof = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_start_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🌊 Записаться на тур")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

def get_progress(step):
    steps = ["⬜", "⬜", "⬜"]
    for i in range(min(step, 3)):
        steps[i] = "✅"
    return "".join(steps)

# --- ТЕКСТЫ ДЛЯ ТУРА ---
TOUR_INFO = """
🌊 *ТУР НА БАЙКАЛ*
📅 *Даты:* 25 февраля - 3 марта

💰 *СТОИМОСТЬ И УСЛОВИЯ ТУРА*
*Стоимость маршрута:* 79 000 ₽

✅ *В СТОИМОСТЬ ВКЛЮЧЕНО:*
✔️ Проживание по маршруту
✔️ Питание: завтрак, ужин — включены
✔️ Экскурсионное сопровождение
✔️ Все активности, указанные в программе
✔️ Профессиональная фото- и видеосъёмка на острове Ольхон с квадрокоптера (дрон)

❌ *ОПЛАЧИВАЕТСЯ ДОПОЛНИТЕЛЬНО:*
— ✈️ Перелёт (за счёт туриста)
— Сувениры
— Обеды, музей, фермы, коньки
— Личные расходы и индивидуальные «хотелки»
"""

PAYMENT_INFO = f"""
💳 *ОПЛАТА ДЕПОЗИТА*

Для бронирования места необходимо внести депозит *20 000 ₽*

📲 *Быстрая оплата:*
[Перейти к оплате]({PAYMENT_LINK})

📌 *Альтернативные реквизиты:*
`+79124591439` (Сбербанк / Т-Банк)
👤 Получатель: Екатерина Б.

📎 *После оплаты пришлите скриншот чека сюда.*
"""

# --- ХЭНДЛЕРЫ БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "🌊 *Добро пожаловать на запись в тур на Байкал!*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{TOUR_INFO}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Для записи на тур заполните короткую анкету.\n\n"
        "Нажмите кнопку ниже, чтобы начать"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_start_kb())

@dp.message(F.text == "🌊 Записаться на тур")
async def start_form(message: types.Message, state: FSMContext):
    await message.answer(
        f"{get_progress(0)}\n**Шаг 1:** Введите ваше **ФИО** полностью:",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        f"{get_progress(1)}\n**Шаг 2:** Напишите ваш **номер телефона**:",
        parse_mode="Markdown",
    )
    await state.set_state(Registration.waiting_for_contact)

@dp.message(Registration.waiting_for_contact, F.text)
async def process_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    data = await state.get_data()

    summary = (
        f"{get_progress(2)}\n*ПРОВЕРЬТЕ ВАШИ ДАННЫЕ:*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 *ФИО:* {data.get('name')}\n"
        f"📞 *Телефон:* {data.get('contact')}\n"
        f"🎯 *Тур:* Байкал (25.02-03.03)\n"
        f"💰 *Стоимость:* 79 000 ₽\n"
        f"💵 *Депозит:* 20 000 ₽\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Если всё верно — подтвердите данные."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📜 Читать оферту", url=OFFER_LINK)],
            [InlineKeyboardButton(text="✅ Все верно, продолжить", callback_data="confirm_ok")],
            [InlineKeyboardButton(text="❌ Заполнить заново", callback_data="restart")],
        ]
    )
    await message.answer(summary, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(Registration.confirm_data)

@dp.callback_query(F.data == "restart")
async def restart_form(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_form(callback.message, state)

@dp.callback_query(F.data == "confirm_ok", Registration.confirm_data)
async def process_confirm(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        f"✅ *ДАННЫЕ ПРИНЯТЫ*\n\n{PAYMENT_INFO}",
        parse_mode="Markdown",
        disable_web_page_preview=False
    )
    await state.set_state(Registration.waiting_for_payment_proof)

@dp.message(Registration.waiting_for_payment_proof, F.photo | F.document)
async def process_payment_proof(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    admin_report = (
        "🔥 *НОВАЯ ЗАЯВКА НА ТУР НА БАЙКАЛ!*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 *ФИО:* {user_data.get('name')}\n"
        f"📞 *Телефон:* {user_data.get('contact')}\n"
        f"🎯 *Тур:* Байкал (25.02-03.03)\n"
        f"💰 *Сумма:* 79 000 ₽\n"
        f"💵 *Депозит:* 20 000 ₽\n"
        f"🆔 *ID:* `{message.from_user.id}`\n"
        f"📅 *Время заявки:* {current_time}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, admin_report, parse_mode="Markdown")
            await message.copy_to(ADMIN_ID)
        except Exception as e:
            logging.error(f"Ошибка отправки админу: {e}")

    await message.answer(
        "✨ *БРОНЬ ПРИНЯТА!*\n\n"
        "Спасибо за вашу заявку! Мы свяжемся с вами в ближайшее время "
        "для уточнения деталей.\n\n"
        "📞 По вопросам: @ваш_контакт",  # Замените на реальный контакт
        reply_markup=get_start_kb(),
        parse_mode="Markdown",
    )
    await state.clear()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle_health_check(request):
    """Эндпоинт для проверки работоспособности"""
    return web.Response(text="Bot is alive and ready for Baikal tour!")

async def start_web_server():
    """Запускает aiohttp сервер для keep-alive"""
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/health", handle_health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")

# --- ЗАПУСК ---
async def main():
    # Настройка бота
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands([
        BotCommand(command="start", description="Начать запись на тур")
    ])

    # Запуск бота и веб-сервера параллельно
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server(),
    )

if __name__ == "__main__":
    try:
        logging.info("Starting Baikal Tour Bot...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
