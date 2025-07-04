import asyncio
import secrets
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота
API_TOKEN = os.getenv("8066163997:AAEDYXXY9L3o3Xn3tgvgjEwpgsz8lkLT1bo")

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# Словари
user_links = {}         # user_id -> token
link_to_user = {}       # token -> user_id
anon_sessions = {}      # sender_id -> recipient_id
active_replies = {}     # recipient_id -> sender_id
link_messages = {}      # user_id -> message_id

# Генерация токена
def generate_token():
    return secrets.token_urlsafe(6)

# Построение текста и клавиатуры
def build_link_text_and_markup(user_id: int, bot_username: str):
    token = user_links[user_id]
    link = f"https://t.me/{bot_username}?start={token}"
    text = f"<b>Твоя ссылка:</b>\n\n{link}"
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Обновить ссылку", callback_data="refresh_link")
    return text, kb.as_markup()

# /start
@dp.message(F.text == "/start")
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"/start от {user_id}")

    if user_id not in user_links:
        token = generate_token()
        user_links[user_id] = token
        link_to_user[token] = user_id
        logger.info(f"Создан токен {token} для пользователя {user_id}")

    bot_username = (await bot.get_me()).username
    text, kb = build_link_text_and_markup(user_id, bot_username)

    sent = await message.answer(text, reply_markup=kb)
    link_messages[user_id] = sent.message_id

# Обновление ссылки
@dp.callback_query(F.data == "refresh_link")
async def refresh_link(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    logger.info(f"{user_id} нажал обновить ссылку")

    old_token = user_links.get(user_id)
    if old_token:
        link_to_user.pop(old_token, None)
        logger.info(f"Удалён старый токен: {old_token}")

    new_token = generate_token()
    user_links[user_id] = new_token
    link_to_user[new_token] = user_id
    logger.info(f"Создан новый токен {new_token} для пользователя {user_id}")

    bot_username = (await bot.get_me()).username
    text, kb = build_link_text_and_markup(user_id, bot_username)

    if user_id in link_messages:
        msg_id = link_messages[user_id]
        try:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=msg_id,
                text=text,
                reply_markup=kb
            )
        except:
            logger.warning("Не удалось обновить сообщение со ссылкой")

    await callback.answer("Ссылка обновлена.")

# Переход по ссылке
@dp.message(F.text.startswith("/start "))
async def handle_token_entry(message: types.Message):
    token = message.text.split(" ", 1)[1].strip()
    user_id = message.from_user.id
    logger.info(f"{user_id} перешёл по ссылке с токеном {token}")

    if token in link_to_user:
        recipient_id = link_to_user[token]
        anon_sessions[user_id] = recipient_id
        logger.info(f"{user_id} теперь может писать {recipient_id}")
        await message.answer("Можешь написать сообщение.")
    else:
        logger.warning("Неверный токен")
        await message.answer("Ссылка устарела или неверна.")

# Обработка сообщений
@dp.message()
async def handle_message(message: types.Message):
    sender_id = message.from_user.id

    # Ответ
    if sender_id in active_replies:
        target_id = active_replies.pop(sender_id)
        logger.info(f"{sender_id} пишет ответ пользователю {target_id}")

        try:
            if message.photo:
                logger.info("Отправляется: фото")
                await bot.send_photo(target_id, message.photo[-1].file_id, caption="📥 Ответ с изображением")
            elif message.sticker:
                logger.info("Отправляется: стикер")
                await bot.send_sticker(target_id, message.sticker.file_id)
            elif message.animation:
                logger.info("Отправляется: GIF")
                await bot.send_animation(target_id, message.animation.file_id, caption="📥 Ответ с GIF")
            elif message.video_note:
                logger.info("Отправляется: видеосообщение")
                await bot.send_video_note(target_id, message.video_note.file_id)
            elif message.video:
                logger.info("Отправляется: видео")
                await bot.send_video(target_id, message.video.file_id, caption="📥 Ответ с видео")
            else:
                logger.info("Отправляется: текст")
                await bot.send_message(target_id, f"📥 Ответ:\n\n{message.text}")

            await message.answer("Ответ отправлен.")
        except Exception as e:
            logger.error(f"Ошибка при отправке ответа: {e}")
            await message.answer("Не удалось отправить ответ.")
        return

    # Первичное сообщение
    if sender_id in anon_sessions:
        target_id = anon_sessions.pop(sender_id)
        logger.info(f"{sender_id} пишет пользователю {target_id}")

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Ответить", callback_data=f"reply_{sender_id}")]
            ]
        )

        try:
            if message.photo:
                logger.info("Пересылается: фото")
                await bot.send_photo(target_id, message.photo[-1].file_id, caption="📩 Изображение", reply_markup=kb)
            elif message.sticker:
                logger.info("Пересылается: стикер")
                await bot.send_sticker(target_id, message.sticker.file_id, reply_markup=kb)
            elif message.animation:
                logger.info("Пересылается: GIF")
                await bot.send_animation(target_id, message.animation.file_id, caption="📩 GIF", reply_markup=kb)
            elif message.video_note:
                logger.info("Пересылается: видеосообщение")
                await bot.send_video_note(target_id, message.video_note.file_id, reply_markup=kb)
            elif message.video:
                logger.info("Пересылается: видео")
                await bot.send_video(target_id, message.video.file_id, caption="📩 Видео", reply_markup=kb)
            else:
                logger.info("Пересылается: текст")
                await bot.send_message(target_id, f"<b>Сообщение:</b>\n\n{message.text}", reply_markup=kb)

            active_replies[target_id] = sender_id
            await message.answer("Сообщение отправлено.")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            await message.answer("Не удалось доставить сообщение.")
    else:
        logger.warning(f"{sender_id} пишет вне сессии")
        await message.answer("Сначала перейди по ссылке, чтобы начать.")

# Обработка нажатия "↩️ Ответить"
@dp.callback_query(F.data.startswith("reply_"))
async def handle_reply_button(callback: types.CallbackQuery):
    try:
        sender_id = int(callback.data.split("_")[1])
        active_replies[callback.from_user.id] = sender_id
        logger.info(f"{callback.from_user.id} нажал ответ пользователю {sender_id}")
        await bot.send_message(callback.from_user.id, "Напиши сообщение — оно будет передано.")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при ответе: {e}")
        await callback.answer("Ошибка.")

# Запуск бота
async def main():
    logger.info("🤖 Бот запущен.")
    me = await bot.get_me()
    logger.info(f"Бот: @{me.username} (ID: {me.id})")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
