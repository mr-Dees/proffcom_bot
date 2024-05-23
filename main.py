# Библиотеки для работы с интерпретатором Python, логированием и многопоточностью
import asyncio
import logging
import sys

# Библиотеки для отправки и получения сообщений от YandexGPT
import json
import requests

# Настройки асинхронного режима при использовании windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Переменны для связи сервисов
from config import TELEGRAM_TOKEN, YANDEX_FOLDER_ID, YANDEX_GPT_API, YANDEX_GPT_URL

# Библиотеки для работы с телеграмм-ботом
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

# Лист для хранения контекста
context_messages = [
    {
        "role": "system",
        "text": "Ты ассистент профкома студентов НГАСУ (Сибстрин). Отвечай кратко и по делу"
    },
]

# Все обработчики должны быть подключены к маршрутизатору (или диспетчеру)
dp = Dispatcher()


# Функция запроса у YandexGPT
async def ask_yandex_gpt(msg: list) -> str:
    response = requests.post(
        # Настраиваем авторизацию с ботом
        YANDEX_GPT_URL,
        headers={
            "Authorization": f"Api-Key {YANDEX_GPT_API}",
            "x-folder-id": YANDEX_FOLDER_ID
        },
        # Указываем настройки бота
        json={
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite/latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,
                "maxTokens": "2000"
            },
            "messages": msg
        },
    )
    # Возвращаем ответ от Яндекса
    return response.json()['result']['alternatives'][0]['message']['text']


# Функция обработки команды /start
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    # Отправляем приветственное сообщение
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")


# Функция обработки обычных сообщений
@dp.message()
async def echo_handler(message: Message) -> None:
    try:
        # Добавляем текущее сообщение от пользователя в контекст беседы
        context_messages.append({"role": "user", "text": message.text})
        # Вывод в консоль текущее сообщение от пользователя и весь контекст диалога
        print("user: ", message.text)
        print("user context_messages: ", context_messages)

        # Запрашиваем ответ на вопрос у Яндекса
        gpt_message = await ask_yandex_gpt(context_messages)
        # Добавляем текущее сообщение от Яндекса в контекст беседы
        context_messages.append({"role": "assistant", "text": gpt_message})
        # Вывод в консоль текущее сообщение от Яндекса и весь контекст диалога
        print("gpt: ", gpt_message)
        print("gpt context_messages: ", context_messages)

        # Отправляем ответ полученный от Яндекса
        await message.answer(gpt_message)
    # Обрабатываем ситуацию когда полученное сообщение имеет недоступный формат
    except TypeError:
        await message.answer("Хорошая попытка!")
    # Обрабатываем все остальные ошибки, которые могут возникнуть
    except Exception as e:
        # Выводи лог об ошибке
        logging.error(f"Неожиданная ошибка в echo_handler: {e}")
        # Отправляем пользователю сообщение об ошибке
        await message.answer("Произошла непредвиденная ошибка.")


# Описываем основную функцию программы
async def main() -> None:
    # Создаем экземпляр класса телеграм-бот для доступа к самому чату и его функционалу
    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Запускаем асинхронную обработку сообщений и команд
    await dp.start_polling(bot)


# Точка входа'
if __name__ == "__main__":
    # Включаем логирование на уровне INFO и выше. Вывод происходит в консоль
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        # Асинхронно запускаем программу
        asyncio.run(main())
    # Если во время выполнения произошла ошибка или прерывание, выводим сообщение об этом
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен!")
