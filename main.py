import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Бот запущен и готов к работе...")

import os
os.environ['no_proxy'] = '*'
os.environ['NO_PROXY'] = '*'

# Импорт необходимых модулей
import requests
from bs4 import BeautifulSoup
import telebot
from telebot import types
from urllib.parse import urljoin
import re
from collections import defaultdict
import time
from dotenv import load_dotenv
from flask import Flask, jsonify
import threading

# Загрузка переменных окружения
load_dotenv()

# Получение токена
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("ОШИБКА: BOT_TOKEN не найден. Проверьте Secrets!")
    exit(1)

# Создание бота
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# Функция для парсинга сайта antiqcar.ru
def parse_antiqcar():
    url = "https://antiqcar.ru/market"
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.5',
        }

        # Создаем сессию с отключенным использованием переменных окружения для прокси
        session = requests.Session()
        session.trust_env = False

        response = session.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        cars = []

        # Ищем все карточки автомобилей
        car_items = soup.select('div.flex-item.mix')

        for item in car_items:
            try:
                # Проверяем, не продан ли автомобиль
                item_classes = ' '.join(item.get('class', [])).lower()
                if 'sold' in item_classes or 'onsale' not in item_classes:
                    continue

                # Проверяем наличие текста "Продано" в карточке
                if "продано" in str(item).lower():
                    continue

                # Проверяем, не является ли это детским автомобилем
                children_brand_span = item.select_one('span[data-brand="Авто для детей"]')
                is_children = children_brand_span is not None

                # Извлекаем бренд из data-brand
                brand_value = "Неизвестно"
                # Сначала ищем в span с data-brand
                brand_span = item.select_one('span[data-brand]')
                if brand_span:
                    brand_value = brand_span.get('data-brand', 'Неизвестно')
                else:
                    # Если нет, пытаемся извлечь из названия
                    name_tag = item.select_one('h2.left strong, h2.left b')
                    if name_tag:
                        name_text = name_tag.text.strip()
                        brand_match = re.search(r'^([A-Za-zА-Яа-я]+(?:[\s\-][A-Za-zА-Яа-я]+)*)', name_text)
                        if brand_match:
                            brand_value = brand_match.group(1).strip()

                # Ищем название автомобиля
                name_tag = item.select_one('h2.left strong, h2.left b')
                name = "Неизвестный автомобиль"
                if name_tag:
                    name = name_tag.text.strip()

                # Ищем фото автомобиля (data-src)
                photo_tag = item.select_one('img.lazyload[data-src]')
                photo_url = None
                if photo_tag:
                    photo_url = photo_tag.get('data-src')
                    if photo_url and not photo_url.startswith('http'):
                        photo_url = urljoin(url, photo_url)
                    photo_url = photo_url.strip()

                # Ищем цену (div с классом right2)
                price_tag = item.select_one('div.right2 strong')
                price = "Цена по запросу"
                if price_tag:
                    price = price_tag.text.strip()
                    price = re.sub(r'\s+', ' ', price).strip()

                # Ищем ссылку на автомобиль
                link_tag = item.select_one('a[href]')
                link = ""
                if link_tag:
                    link = link_tag['href']
                    if link and not link.startswith('http'):
                        link = urljoin(url, link)

                # Ищем информацию о наличии
                location_tag = item.select_one('div.right2 span[style*="font-size:8pt"]')
                location = "Город не указан"
                if location_tag:
                    # Берем текст целиком без извлечения только города
                    location = location_tag.text.strip()

                # Определяем категорию
                category = 'retro'
                if is_children:
                    category = 'children'

                # Добавляем автомобиль в список
                if name != "Неизвестный автомобиль" and brand_value != "Неизвестно" and brand_value:
                    cars.append({
                        'name': name,
                        'brand': brand_value,
                        'price': price,
                        'photo': photo_url,
                        'link': link,
                        'location': location,  # Теперь содержит полный текст "В наличии в Москве"
                        'year': "Год не указан",
                        'source': 'antiqcar',
                        'category': category
                    })
            except Exception as e:
                logger.error(f"Ошибка при обработке карточки antiqcar: {e}")
                continue

        return cars
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при парсинге antiqcar: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при парсинге antiqcar: {e}")
        return []

# Функция для парсинга сайта antarmotors.ru
def parse_antarmotors():
    url = "https://antarmotors.ru/market"
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.5',
        }

        # Создаем сессию с отключенным использованием переменных окружения для прокси
        session = requests.Session()
        session.trust_env = False

        response = session.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        cars = []

        # Ищем все карточки автомобилей
        car_items = soup.select('div.flex-item.mix')

        for item in car_items:
            try:
                # Проверяем, не продан ли автомобиль
                item_classes = ' '.join(item.get('class', [])).lower()
                if 'sold' in item_classes or 'onsale' not in item_classes:
                    continue

                # Проверяем наличие текста "Продано" в карточке
                if "продано" in str(item).lower():
                    continue

                # Проверяем, не является ли это детским автомобилем
                children_brand_span = item.select_one('span[data-brand="Авто для детей"]')
                is_children = children_brand_span is not None

                # Извлекаем бренд из data-brand
                brand_value = "Неизвестно"
                # Сначала ищем в span с data-brand
                brand_span = item.select_one('span[data-brand]')
                if brand_span:
                    brand_value = brand_span.get('data-brand', 'Неизвестно')
                else:
                    # Если нет, пытаемся извлечь из названия
                    name_tag = item.select_one('h2.left strong, h2.left b')
                    if name_tag:
                        name_text = name_tag.text.strip()
                        brand_match = re.search(r'^([A-Za-zА-Яа-я]+(?:[\s\-][A-Za-zА-Яа-я]+)*)', name_text)
                        if brand_match:
                            brand_value = brand_match.group(1).strip()

                # Ищем название автомобиля
                name_tag = item.select_one('h2.left strong, h2.left b')
                name = "Неизвестный автомобиль"
                if name_tag:
                    name = name_tag.text.strip()

                # Ищем фото автомобиля (data-src)
                photo_tag = item.select_one('img.lazyload[data-src]')
                photo_url = None
                if photo_tag:
                    photo_url = photo_tag.get('data-src')
                    if photo_url and not photo_url.startswith('http'):
                        photo_url = urljoin(url, photo_url)
                    photo_url = photo_url.strip()

                # Ищем цену (div с классом right2)
                price_tag = item.select_one('div.right2 strong')
                price = "Цена по запросу"
                if price_tag:
                    price = price_tag.text.strip()
                    price = re.sub(r'\s+', ' ', price).strip()

                # Ищем ссылку на автомобиль
                link_tag = item.select_one('a[href]')
                link = ""
                if link_tag:
                    link = link_tag['href']
                    if link and not link.startswith('http'):
                        link = urljoin(url, link)

                # Ищем информацию о наличии
                location_tag = item.select_one('div.right2 span[style*="font-size:8pt"]')
                location = "Город не указан"
                if location_tag:
                    # Берем текст целиком без извлечения только города
                    location = location_tag.text.strip()

                # Определяем категорию
                category = 'new'
                if is_children:
                    category = 'children'

                # Добавляем автомобиль в список
                if name != "Неизвестный автомобиль" and brand_value != "Неизвестно" and brand_value:
                    cars.append({
                        'name': name,
                        'brand': brand_value,
                        'price': price,
                        'photo': photo_url,
                        'link': link,
                        'location': location,  # Теперь содержит полный текст "В наличии в Москве"
                        'year': "Год не указан",
                        'source': 'antarmotors',
                        'category': category
                    })
            except Exception as e:
                logger.error(f"Ошибка при обработке карточки antarmotors: {e}")
                continue

        return cars
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при парсинге antarmotors: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при парсинге antarmotors: {e}")
        return []

# Основная функция для парсинга всех сайтов
def parse_all_cars():
    cars = []

    # Парсим ретро автомобили
    antiqcar_cars = parse_antiqcar()
    cars.extend(antiqcar_cars)

    # Парсим новые автомобили
    antarmotors_cars = parse_antarmotors()
    cars.extend(antarmotors_cars)

    return cars

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Первая кнопка "Все автомобили" во всю строку
    markup.row(types.KeyboardButton("🔍 Все автомобили"))
    # Три кнопки в одну строку
    markup.row(
        types.KeyboardButton("🚘 Новые"),
        types.KeyboardButton("🚗 Ретро"),
        types.KeyboardButton("👶 Детские")
    )
    # Кнопка помощи
    markup.row(types.KeyboardButton("ℹ️ Помощь"))

    welcome_text = """<b>Мы - Сообщество автомобильных энтузиастов прекрасно понимаем: иногда нужно купить авто сразу, а иногда – найти именно ту уникальную модель, которая покорила ваше сердце.</b>

• Готовые решения: На нашем складе и площадках всегда представлен тщательно подобранный парк автомобилей из наличия. Это проверенные, подготовленные к передаче машины различных марок, моделей и комплектаций.
• Экономия времени: Не хотите или не можете ждать? Выбирайте из готовых вариантов! Осмотрите, протестируйте и уезжайте за рулем своего нового авто буквально в день обращения.
• Прозрачность и гарантии: Каждое авто из наличия проходит предпродажную подготовку. Мы предоставляем полную информацию о состоянии и истории автомобиля.


Загляните в наш каталог – ваш идеальный автомобиль, возможно, уже ждет вас!

<b>Основные функции:</b>

• <b>Все автомобили</b> - объединенный поиск по всем доступным автомобилям
• <b>Новые</b> - просмотр новых премиальных автомобилей
• <b>Ретро</b> - просмотр классических автомобилей
• <b>Детские</b> - просмотр детских автомобилей

Нажмите на кнопку ниже для начала поиска."""

    bot.reply_to(message, welcome_text, reply_markup=markup, disable_web_page_preview=True)

# Обработчик текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text == "🚗 Ретро":
        show_brands(message, category='retro')
    elif message.text == "🚘 Новые":
        show_brands(message, category='new')
    elif message.text == "👶 Детские":
        show_brands(message, category='children')
    elif message.text == "🔍 Все автомобили":
        show_brands(message, category=None)
    elif message.text == "ℹ️ Помощь":
        show_help(message)
    else:
        bot.reply_to(message, "Пожалуйста, используйте кнопки меню.")

def show_brands(message, category=None, page=1):
    msg = bot.send_message(message.chat.id, "⏳ Ищу доступные марки автомобилей...")

    cars = parse_all_cars()

    # Фильтруем по категории
    if category:
        cars = [car for car in cars if car.get('category') == category]

    # Удаляем предыдущее сообщение "Ищу..."
    try:
        bot.delete_message(message.chat.id, msg.message_id)
    except:
        pass

    if not cars:
        # Если нет детских автомобилей, показываем специальное сообщение
        if category == 'children':
            error_msg = """ℹ️ В настоящее время в категории "Детские" нет доступных моделей.

Проверьте, пожалуйста, позже. Возможно, информация обновится.

Вы можете вернуться в главное меню:"""
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            # Первая кнопка "Все автомобили" во всю строку
            markup.row(types.KeyboardButton("🔍 Все автомобили"))
            # Три кнопки в одну строку
            markup.row(
                types.KeyboardButton("🚘 Новые"),
                types.KeyboardButton("🚗 Ретро"),
                types.KeyboardButton("👶 Детские")
            )
            # Кнопка помощи
            markup.row(types.KeyboardButton("ℹ️ Помощь"))
            bot.reply_to(message, error_msg, reply_markup=markup)
            return
        else:
            error_msg = """❌ Не удалось загрузить список автомобилей.

Возможные причины:
1. Сайты временно недоступны
2. Структура сайтов изменилась
3. Требуется обновление парсера

Попробуйте позже или свяжитесь с поддержкой."""
            bot.reply_to(message, error_msg)
            return

    # Группируем по брендам, используя оригинальное значение
    brands = {}
    for car in cars:
        # Используем оригинальное значение brand для группировки
        brand_key = car['brand'].lower().strip()

        if brand_key not in brands:
            brands[brand_key] = {
                'display_name': car['brand'],  # Сохраняем оригинальное значение для отображения
                'cars': []
            }

        brands[brand_key]['cars'].append(car)

    # Сортируем марки по алфавиту
    sorted_brands = sorted(brands.items(), key=lambda x: x[1]['display_name'])

    # Пагинация
    brands_per_page = 15
    total_pages = max(1, (len(sorted_brands) + brands_per_page - 1) // brands_per_page)
    start_idx = (page - 1) * brands_per_page
    end_idx = start_idx + brands_per_page
    current_page_brands = sorted_brands[start_idx:end_idx]

    # Определяем заголовок в зависимости от категории
    if category == 'retro':
        header = "ретро автомобилей"
    elif category == 'new':
        header = "новых автомобилей"
    elif category == 'children':
        header = "детских автомобилей"
    else:
        header = "автомобилей"

    # Отправляем список марок
    response = f"<b>🔤 Доступные марки {header} (страница {page} из {total_pages}):</b>\n\n"
    for i, (brand_key, brand_data) in enumerate(current_page_brands, 1):
        response += f"{(page-1)*brands_per_page + i}. <b>{brand_data['display_name']}</b> - {len(brand_data['cars'])} моделей\n"

    response += "\nВыберите марку из списка ниже:"

    # Создаем клавиатуру с марками
    markup = types.InlineKeyboardMarkup(row_width=1)

    # Добавляем кнопки для марок на текущей странице
    for brand_key, brand_data in current_page_brands:
        # Формируем callback_data в зависимости от наличия категории
        if category:
            callback_data = f"brand_{brand_key}_{category}"
        else:
            callback_data = f"brand_{brand_key}"

        btn = types.InlineKeyboardButton(
            f"{brand_data['display_name']} ({len(brand_data['cars'])})", 
            callback_data=callback_data
        )
        markup.add(btn)

    # Добавляем навигацию по страницам
    pagination_row = []
    if page > 1:
        if category:
            pagination_row.append(types.InlineKeyboardButton("◀️ Назад", callback_data=f"page_{page-1}_{category}"))
        else:
            pagination_row.append(types.InlineKeyboardButton("◀️ Назад", callback_data=f"page_{page-1}"))
    if page < total_pages:
        if category:
            pagination_row.append(types.InlineKeyboardButton("Вперед ▶️", callback_data=f"page_{page+1}_{category}"))
        else:
            pagination_row.append(types.InlineKeyboardButton("Вперед ▶️", callback_data=f"page_{page+1}"))

    if pagination_row:
        markup.row(*pagination_row)

    bot.send_message(message.chat.id, response, reply_markup=markup)

def show_help(message):
    help_text = """<b>ℹ️ Помощь по использованию бота</b>


<b>Как использовать:</b>
1. Нажмите на кнопку "Все автомобили", "Новые", "Ретро" или "Детские"
2. Выберите интересующую вас марку
3. Получите информацию об автомобилях


<b>Важно:</b> 
• Бот показывает только автомобили, которые находятся в наличии
• Каждый автомобиль отображается в отдельном сообщении с фото (если доступно)
• Для уточнения деталей используйте ссылки на сайт

☎️ <b>+79037240147</b> (WhatsApp, Telegram)

Для начала работы нажмите /start"""

    bot.send_message(message.chat.id, help_text, disable_web_page_preview=True)

# Обработчик callback-запросов
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        if call.data.startswith("brand_"):
            parts = call.data.split("_")
            brand_key = parts[1]
            category = parts[2] if len(parts) > 2 else None

            cars = parse_all_cars()

            # Фильтруем по категории
            if category:
                cars = [car for car in cars if car.get('category') == category]

            # Фильтруем по оригинальному значению бренда
            brand_cars = [car for car in cars if car['brand'].lower().strip() == brand_key]

            if not brand_cars:
                bot.answer_callback_query(call.id, "Не удалось найти автомобили этой марки")
                return

            # Находим оригинальное название марки
            original_brand = brand_cars[0]['brand']

            # Отправляем информацию об автомобилях этой марки
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🚗 <b>Автомобили марки {original_brand}:</b>",
                parse_mode='HTML'
            )

            # Отправляем каждый автомобиль в отдельном сообщении
            for i, car in enumerate(brand_cars, 1):
                car_info = f"<b>#{i} {car['name']}</b>\n\n"

                # Для новых авто показываем год, для ретро - нет
                if car.get('category') == 'new' and car['year'] != "Год не указан":
                    car_info += f"📅 <b>Год выпуска:</b> {car['year']}\n"

                # Используем полный текст о наличии
                car_info += f"📍 <b>Наличие:</b> {car['location']}\n"

                car_info += f"💰 <b>Цена:</b> {car['price']}"

                if car.get('link'):
                    car_info += f"\n\n🔗 <a href='{car['link']}'>Подробнее на сайте</a>"

                # Добавляем контакт внизу карточки
                car_info += f"\n\n☎️ <b>+79037240147</b> (WhatsApp, Telegram)"

                # Отправляем фото и описание отдельными сообщениями
                if car.get('photo'):
                    try:
                        bot.send_photo(
                            call.message.chat.id, 
                            car['photo'],
                            caption=car_info
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки фото: {e}")
                        bot.send_message(
                            call.message.chat.id, 
                            f"⚠️ Фото недоступно\n\n{car_info}",
                            disable_web_page_preview=True
                        )
                else:
                    bot.send_message(
                        call.message.chat.id, 
                        car_info,
                        disable_web_page_preview=True
                    )

                # Небольшая пауза между отправкой
                time.sleep(0.5)

            # Кнопка для возврата
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            # Первая кнопка "Все автомобили" во всю строку
            markup.row(types.KeyboardButton("🔍 Все автомобили"))
            # Три кнопки в одну строку
            markup.row(
                types.KeyboardButton("🚘 Новые"),
                types.KeyboardButton("🚗 Ретро"),
                types.KeyboardButton("👶 Детские")
            )
            # Кнопка помощи
            markup.row(types.KeyboardButton("ℹ️ Помощь"))

            bot.send_message(
                call.message.chat.id,
                "✅ Загрузка завершена! Выберите следующее действие:",
                reply_markup=markup
            )

        elif call.data.startswith("page_"):
            parts = call.data.split("_")
            page = int(parts[1])
            category = parts[2] if len(parts) > 2 else None

            # Редактируем текущее сообщение, заменяя его на новую страницу
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
            # Отправляем новую страницу
            show_brands(call.message, category=category, page=page)

    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Произошла ошибка: {str(e)}")
        logger.error(f"Callback error: {e}")

# Запуск веб-сервера для предотвращения засыпания на Replit
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "active", "message": "Бот для поиска ретро автомобилей работает!"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

def keep_alive():
    """Постоянно отправляет запросы к собственному серверу для предотвращения засыпания"""
    logger.info("Запуск keep_alive потока")
    while True:
        try:
            logger.info("Отправка keep-alive запроса")
            # Отправляем запрос к нашему же серверу
            requests.get('http://127.0.0.1:8080/health')
            # Отправляем запрос к внешнему сервису для дополнительной активности
            requests.get('https://api.github.com')
        except Exception as e:
            logger.error(f"Ошибка в keep_alive: {str(e)}")
        time.sleep(300)  # Каждые 5 минут

def run_server():
    app.run(host='0.0.0.0', port=8080)

# Запускаем веб-сервер и keep-alive в отдельных потоках
server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

keep_alive_thread = threading.Thread(target=keep_alive)
keep_alive_thread.daemon = True
keep_alive_thread.start()

# Запуск бота
if __name__ == '__main__':
    logger.info("Бот запущен и готов к работе...")
    bot.infinity_polling()
