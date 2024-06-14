# Библиотеки для правильной и удобной работы с интерпретатором Python
import asyncio  # Асинхронное программирование
import logging  # Логирование событий
import sys  # Доступ к параметрам и функциям операционной системы
import os  # Взаимодействие с операционной системой

# Библиотеки для отправки и получения сообщений от YandexGPT
import requests  # Отправка HTTP-запросов

# Библиотеки для работы с базой данных
import lancedb  # Работа с векторными хранилищами данных
import pickle  # Сериализация и десериализация объектов Python

# Переменные для связи сервисов
from config import TELEGRAM_TOKEN, YANDEX_FOLDER_ID, YANDEX_GPT_API, YANDEX_GPT_URL, SOURCE_DIR, DB_DIR

# Библиотеки для работы с телеграмм-ботом
from aiogram import Bot, Dispatcher, html  # Основные классы для создания телеграмм-бота
from aiogram.client.default import DefaultBotProperties  # Настройки бота по умолчанию
from aiogram.enums import ParseMode  # Режимы парсинга сообщений
from aiogram.filters import CommandStart  # Фильтр для команды /start
from aiogram.types import Message  # Класс для представления сообщений

# Библиотеки для работы с langchain'ом
from langchain_community.embeddings import HuggingFaceEmbeddings  # Работа с эмбеддингами от HuggingFace
from langchain_community.vectorstores import LanceDB  # Работа с векторными хранилищами данных
from langchain_community.document_transformers import LongContextReorder  # Перестановка контекстных фрагментов
from langchain.docstore.document import Document  # Представление документов
from langchain.text_splitter import RecursiveCharacterTextSplitter  # Рекурсивное разбиение текста на части

# Настройки асинхронного режима при использовании windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# подключение всех обработчиков к диспетчеру
dp = Dispatcher()


# Переработанный класс DirectoryLoader из библиотеки langchain_community.document_loaders из-за работы на windows
class CustomFileLoader:
    # Инициализация класса с указанием директории и флага рекурсивного поиска
    def __init__(self, source_dir, recursive=False):
        self.source_dir = source_dir
        self.recursive = recursive

    # Метод для загрузки файлов из указанной директории
    def load(self):
        files = []
        # Проверка на существование директории
        if not os.path.exists(self.source_dir):
            # Если директория не существует, выбрасываем исключение
            raise FileNotFoundError(f"Директория {self.source_dir} не существует.")
        # Проверка на то, что это действительно директория
        if not os.path.isdir(self.source_dir):
            # Если указана не директория, выбрасываем исключение
            raise NotADirectoryError(f"{self.source_dir} не является директорией.")

        # Проход по директории и поддиректориям (если recursive=True)
        for root, _, filenames in os.walk(self.source_dir):
            for filename in filenames:
                # Формирование полного пути к файлу
                file_path = os.path.join(root, filename)
                # Открытие файла и чтение его содержимого
                with open(file_path, 'r', encoding='utf-8') as load_file:
                    content = load_file.read()
                # Добавление содержимого файла и метаданных в список
                files.append(Document(page_content=content, metadata={'source': file_path}))
            # Если рекурсивный поиск отключен, прерываем цикл после прохода по указанной директории
            if not self.recursive:
                break

        # Проверка на наличие файлов в директории
        if not files:
            # Если в директории нет файлов, выбрасываем исключение
            raise FileNotFoundError(f"В директории {self.source_dir} нет файлов.")
        # Возвращаем список загруженных файлов
        return files


# Функция запроса у YandexGPT
async def ask_yandex_gpt(msg: list) -> str:
    # Отправляем ПОСТ-запрос на Yandex Cloud
    response = requests.post(
        # Указываем URL для обращения
        YANDEX_GPT_URL,
        # Указываем способ авторизации с ботом
        headers={
            "Authorization": f"Api-Key {YANDEX_GPT_API}",
            "x-folder-id": YANDEX_FOLDER_ID
        },
        # Указываем настройки бота
        json={
            # Указание модели YandexGPT
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite/rc",
            # Настройки генерации текста
            "completionOptions": {
                "stream": False,
                "temperature": 0.825,
                "maxTokens": "512"
            },
            # Сообщение для отправки
            "messages": msg
        },
    )
    # Получаем ответ и преобразовываем в формат JSON
    response_json = response.json()
    # Если ответ был получен, то возвращаем его
    if ('result' in response_json and 'alternatives' in response_json['result']
            and len(response_json['result']['alternatives']) > 0):
        return response_json['result']['alternatives'][0]['message']['text']
    # Если ответ НЕ был получен, то возвращаем ошибку
    else:
        return "Ошибка: пустой ответ от YandexGPT"


# Функция обработки команды /start
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    # Отправляем приветственное сообщение
    await message.answer(f"Привет, {html.bold(message.from_user.full_name)}!")


# Функция обработки обычных сообщений
@dp.message()
async def echo_handler(message: Message) -> None:
    try:
        # Получаем релевантные документы на основе полученного сообщения
        results = retriever.invoke(message.text)
        # Если данные получены, то начинаем работу запросом пользователя
        if results:
            # Перемещаем наиболее релевантные куски к началу и концу выборки
            results = LongContextReorder().transform_documents(results)

            # Добавляем все релевантные куски в context
            context = "\n".join([doc.page_content for doc in results])
            # Создаем шаблон содержаний инструкцию, контекст и вопрос пользователя
            sending_template = [
                {
                    "role": "system",
                    "text": f"""
Ты умный ассистент команды Профкома студентов НГАСУ (Сибстрин).
Твоя единственная задача отвечать на вопросы которые задают студенты нашего вуза.
Ты знаешь ответ на все вопросы которые касаются студенчества и профсоюзной поддержке.
Ты не знаешь ни одного языка программирования.
"""
                },
                {
                    "role": "user",
                    "text": f"""
Прочитай текст в теге info и предоставь один, точный ответ именно на вопрос из тега question и только на него, соблюдая все условия.

Если в теге question написано что-то не требующее информации из тега info - не используй его.
Пример таких тем: приветствие, похвала, прощание, благодарность, оскорбление, вопросы о личности и возможностях, Smalltalk и тому подобные.  

Если у тебя просят ссылку (url) которой нет в теге info напиши, что у тебя нет данной ссылки.
Если в теге info есть ссылка, дополняй ей свой ответ.
Выдумывать ссылки и контактную информацию запрещено.

Если вопрос будет касаться программирования или написания или тестирования кода напиши, что ты не умеешь этого делать.

[info]{context}[/info]
[question]{message.text}[/question]
"""
                },
            ]
            # Отправка полученного шаблона в YandexGPT
            gpt_message = await ask_yandex_gpt(sending_template)
            # Отправка сгенерированного ответа пользователю
            await message.answer(gpt_message)
            # Вывод отладочной информации
            print("context_messages: ", sending_template)
            print('=' * 50)
            print("gpt_message: ", gpt_message)
            print('=' * 50)

        # Если данные НЕ получены, то отправляем пользователю сообщение об ошибке
        else:
            await message.answer("К сожалению, сейчас я не смогу ответить на ваш вопрос :с")
    # Если было вызвано исключение несовместимости типов
    except TypeError as e:
        # Выводим в логи и информируем пользователей
        logging.error(f"Ошибка TypeError ошибка в echo_handler: {e}")
        await message.answer("К сожалению, сейчас я не смогу ответить на ваш вопрос :с")
    # Если было вызвано любое другое исключение
    except Exception as e:
        # Выводим в логи и информируем пользователей
        logging.error(f"Ошибка Exception ошибка в echo_handler: {e}")
        await message.answer("К сожалению, сейчас я не смогу ответить на ваш вопрос :с")


# Описываем основную функцию программы
async def main() -> None:
    # Создаем экземпляр класса телеграм-бот для доступа к самому чату и его функционалу
    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Запускаем асинхронную обработку сообщений и команд
    await dp.start_polling(bot)


# Точка входа
if __name__ == "__main__":
    try:
        # Включаем логирование на уровне INFO и выше. Вывод происходит в консоль
        logging.basicConfig(level=logging.INFO, stream=sys.stdout)

        # Создание директорию, если она не существует
        os.makedirs(DB_DIR, exist_ok=True)

        # Пробуем считать данные из файлов
        embeddings_file = os.path.join(DB_DIR, "embeddings.pkl")
        fragments_file = os.path.join(DB_DIR, "fragments.pkl")

        # Если в системе есть созданные ранее эмбеддинги, то просто загружаем их
        if os.path.exists(embeddings_file) and os.path.exists(fragments_file):
            logging.info("ЗАГРУЗКА СУЩЕСТВУЮЩИХ ЭМБЕДДИНГОВ")
            with open(embeddings_file, 'rb') as f:
                embeddings = pickle.load(f)
            with open(fragments_file, 'rb') as f:
                fragments = pickle.load(f)
            logging.info("ЗАГРУЗКА УСПЕШНО ЗАВЕРШЕНА")
        # Если в системе НЕТ созданных ранее эмбеддингов, то создаем их
        else:
            logging.info("СОЗДАНИЕ НОВЫХ ЭМБЕДДИНГОВ")
            # Разбитие слов на фрагменты
            loader = CustomFileLoader(SOURCE_DIR, recursive=True)
            splitter = RecursiveCharacterTextSplitter(chunk_size=150, chunk_overlap=25)
            fragments = splitter.create_documents([x.page_content for x in loader.load()])

            # Вычисление эмбеддингов
            embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large")
            sample_vec = embeddings.embed_query("Профком")

            # Сохранение эмбеддингов и фрагментов
            with open(embeddings_file, 'wb') as f:
                pickle.dump(embeddings, f)
            with open(fragments_file, 'wb') as f:
                pickle.dump(fragments, f)
            logging.info("СОЗДАНИЕ УСПЕШНО ЗАВЕРШЕНО")

        # Устанавливаем соединение с СУБД
        db = lancedb.connect(DB_DIR)
        # Если в системе есть созданная ранее таблица индексов, то просто загружаем ее
        if "vector_index" in db.table_names():
            logging.info("ЗАГРУЗКА СУЩЕСТВУЮЩЕЙ ВЕКТОРНОЙ БАЗЫ ДАННЫХ")
            table = db.open_table("vector_index")
            logging.info("ЗАГРУЗКА УСПЕШНО ЗАВЕРШЕНА")
        # Если в системе НЕТ созданной ранее таблицы индексов, то создаем ее
        else:
            logging.info("СОЗДАНИЕ НОВОЙ ВЕКТОРНОЙ БАЗЫ ДАННЫХ")
            table = db.create_table(
                "vector_index",
                data=[{
                    "vector": embeddings.embed_query("Профком"),
                    "text": "Профком",
                    "id": "1",
                }],
                mode="overwrite")
            logging.info("СОЗДАНИЕ УСПЕШНО ЗАВЕРШЕНО")

        # Индексируем все документы
        db = LanceDB.from_documents(fragments, embeddings, connection=table)

        # Настраиваем количество необходимых релевантны кусков
        retriever = db.as_retriever(search_kwargs={"k": 3})

        # Запускаем программу в асинхронном режиме
        asyncio.run(main())

    # Если было вызвано исключение выхода или прерывания
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен!")
    # Если было вызвано исключение обработке несуществующего файла
    except FileNotFoundError as e:
        logging.error(f"Ошибка FileNotFoundError при инициализации программы: {e}")
    # Если было вызвано исключение при обработке директории
    except NotADirectoryError as e:
        logging.error(f"Ошибка NotADirectoryError при инициализации программы: {e}")
    # Если было вызвано любое другое исключение
    except Exception as e:
        logging.error(f"Ошибка Exception при инициализации программы: {e}")
