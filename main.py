import asyncio
import logging
import sys

from config import TOKEN
from os import getenv

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message


# Все обработчики должны быть подключены к маршрутизатору (или диспетчеру)
dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    Этот обработчик получает сообщения с помощью команды `/start`
    """
    # Большинство объектов event имеют псевдонимы для методов API, которые могут быть вызваны в контексте событий
    # Например, если вы хотите ответить на входящее сообщение, вы можете использовать псевдоним "message.answer(...)"
    # и целевой чат будет передан в :ref:`aiogram.methods.send_message.SendMessage`
    # метод автоматически или вызвать метод API напрямую через
    # Экземпляр бота: `bot.send_message(chat_id=message.chat.id, ...)`
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")


@dp.message()
async def echo_handler(message: Message) -> None:
    """
    Обработчик отправит полученное сообщение обратно отправителю.
    По умолчанию обработчик сообщений обрабатывает все типы сообщений (например, текст, фотографию, стикер и т.д.).
    """
    try:
        # Отправить копию полученного сообщения
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        # Не все типы поддерживаются для копирования
        await message.answer("Хорошая попытка!")


async def main() -> None:
    # Инициализируйте экземпляр бота свойствами бота по умолчанию, которые будут передаваться во все вызовы API
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Диспетчеризация событий запуска
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
