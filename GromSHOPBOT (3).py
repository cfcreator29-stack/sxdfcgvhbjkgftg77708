import telebot
from telebot import types
import requests
import sqlite3
import time
import threading
from datetime import datetime, timedelta

# Конфигурация
TOKEN = '8215145226:AAERCkoH4Y2j0aIPJrc9uymZVTgu7-QXnbQ'
API_TOKEN = '541534:AAAGUhIbTihWonc3E5JW5JNgT3T5eP0SRLx'
ADMIN_ID = 8535260202

# Настройки
MIN_SELL_PRICE = 10
MIN_DEPOSIT_AMOUNT = 5
DEPOSIT_COMMISSION = 0.07
SALE_COMMISSION = 0.10
HOLDING_HOURS = 1

USDT_TO_RUB = 75

bot = telebot.TeleBot(TOKEN)

def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        balance_rub REAL DEFAULT 0.0,
        join_date TEXT,
        days_in_bot INTEGER DEFAULT 0,
        notification_enabled INTEGER DEFAULT 1
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        file_name TEXT,
        description TEXT,
        file_id TEXT,
        price_rub REAL,
        created_at TEXT,
        is_sold INTEGER DEFAULT 0,
        sold_at TEXT,
        buyer_id INTEGER,
        seller_balance_added INTEGER DEFAULT 0,
        notification_sent INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount_rub REAL,
        amount_usdt REAL,
        type TEXT,
        status TEXT,
        invoice_id TEXT,
        created_at TEXT,
        completed_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mailing_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        content_type TEXT,
        message_id INTEGER,
        sent_count INTEGER,
        created_at TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS held_balances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        file_id INTEGER,
        amount_rub REAL,
        hold_until TEXT,
        released INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (file_id) REFERENCES files (id)
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, notification_enabled FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

def get_users_with_notifications():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE notification_enabled = 1')
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

def add_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    join_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, join_date)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, join_date))
    conn.commit()
    conn.close()

def update_balance_rub(user_id, amount_rub):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance_rub = balance_rub + ? WHERE user_id = ?', 
                  (amount_rub, user_id))
    conn.commit()
    conn.close()

def set_balance_rub(user_id, new_balance_rub):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance_rub = ? WHERE user_id = ?', 
                  (new_balance_rub, user_id))
    conn.commit()
    conn.close()

def toggle_notifications(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET notification_enabled = NOT notification_enabled WHERE user_id = ?', (user_id,))
    conn.commit()
    cursor.execute('SELECT notification_enabled FROM users WHERE user_id = ?', (user_id,))
    status = cursor.fetchone()[0]
    conn.close()
    return status

def add_file(user_id, file_name, description, file_id, price_rub):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    INSERT INTO files (user_id, file_name, description, file_id, price_rub, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, file_name, description, file_id, price_rub, created_at))
    
    file_id_db = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return file_id_db

def mark_notification_sent(file_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE files SET notification_sent = 1 WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()

def get_user_files(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM files WHERE user_id = ? AND is_sold = 0', (user_id,))
    files = cursor.fetchall()
    conn.close()
    return files

def get_user_file_by_name(user_id, file_name):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM files WHERE user_id = ? AND file_name = ? AND is_sold = 0', (user_id, file_name))
    file = cursor.fetchone()
    conn.close()
    return file

def get_all_files():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM files WHERE is_sold = 0')
    files = cursor.fetchall()
    conn.close()
    return files

def get_file_by_id(file_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM files WHERE id = ?', (file_id,))
    file = cursor.fetchone()
    conn.close()
    return file

def mark_file_sold(file_id, buyer_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    sold_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('UPDATE files SET is_sold = 1, sold_at = ?, buyer_id = ? WHERE id = ?', 
                  (sold_at, buyer_id, file_id))
    conn.commit()
    conn.close()

def delete_file(file_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM files WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()

def add_transaction(user_id, amount_rub, amount_usdt, type, status, invoice_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    INSERT INTO transactions (user_id, amount_rub, amount_usdt, type, status, invoice_id, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, amount_rub, amount_usdt, type, status, invoice_id, created_at))
    conn.commit()
    conn.close()

def complete_transaction(invoice_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('UPDATE transactions SET status = ?, completed_at = ? WHERE invoice_id = ?', 
                  ('completed', completed_at, invoice_id))
    conn.commit()
    conn.close()

def add_held_balance(user_id, file_id, amount_rub):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    hold_until = (datetime.now() + timedelta(hours=HOLDING_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    INSERT INTO held_balances (user_id, file_id, amount_rub, hold_until)
    VALUES (?, ?, ?, ?)
    ''', (user_id, file_id, amount_rub, hold_until))
    conn.commit()
    conn.close()
    return hold_until

def release_held_balances():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    SELECT * FROM held_balances 
    WHERE hold_until <= ? AND released = 0
    ''', (now,))
    held_balances = cursor.fetchall()
    
    released_count = 0
    for balance in held_balances:
        update_balance_rub(balance[1], balance[3])
        
        cursor.execute('UPDATE held_balances SET released = 1 WHERE id = ?', (balance[0],))
        
        cursor.execute('UPDATE files SET seller_balance_added = 1 WHERE id = ?', (balance[2],))
        
        cursor.execute('SELECT file_name FROM files WHERE id = ?', (balance[2],))
        file_info = cursor.fetchone()
        file_name = file_info[0] if file_info else "Файл"
        
        released_count += 1
        
        try:
            bot.send_message(balance[1], 
                           f"✅ Средства от продажи поступили на баланс!\n\n"
                           f"📁 Файл: {file_name}\n"
                           f"💰 Сумма: {balance[3]:.2f} RUB\n"
                           f"⏰ Удержание: {HOLDING_HOURS} час(ов)")
        except Exception as e:
            print(f"Ошибка при уведомлении пользователя {balance[1]}: {e}")
    
    conn.commit()
    conn.close()
    
    return released_count

def add_mailing_record(admin_id, content_type, message_id, sent_count):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    INSERT INTO mailing_history (admin_id, content_type, message_id, sent_count, created_at)
    VALUES (?, ?, ?, ?, ?)
    ''', (admin_id, content_type, message_id, sent_count, created_at))
    conn.commit()
    conn.close()

def notify_users_about_new_file(file_id):
    file = get_file_by_id(file_id)
    if not file:
        return
    
    users = get_users_with_notifications()
    
    seller = get_user(file[1])
    seller_username = seller[2] if seller and seller[2] else 'Пользователь'
    
    price_usdt = file[5] / USDT_TO_RUB
    
    notification_text = f"""
🎉 НОВЫЙ ФАЙЛ В МАГАЗИНЕ! 🎉

📁 Название: {file[2]}
💰 Цена: {file[5]:.2f} RUB | {price_usdt:.2f} USDT

📝 Описание:
{file[3]}

💡 Перейдите в магазин чтобы купить!
    """
    
    sent_count = 0
    failed_count = 0
    
    for user_id in users:
        if user_id == file[1]:
            continue
            
        try:
            markup = types.InlineKeyboardMarkup()
            btn = types.InlineKeyboardButton('🛒 Перейти в магазин', callback_data='open_shop')
            markup.add(btn)
            
            bot.send_message(user_id, notification_text, reply_markup=markup)
            sent_count += 1
            time.sleep(0.05)
        except Exception as e:
            failed_count += 1
            print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
    
    mark_notification_sent(file_id)
    
    print(f"Уведомления о новом файле #{file_id} отправлены: {sent_count} успешно, {failed_count} с ошибками")
    
    try:
        bot.send_message(ADMIN_ID, 
                        f"📊 Уведомления о новом файле:\n"
                        f"📁 {file[2]}\n"
                        f"✅ Отправлено: {sent_count}\n"
                        f"❌ Ошибок: {failed_count}")
    except:
        pass

def get_pay_link(amount_usdt):
    try:
        headers = {"Crypto-Pay-API-Token": API_TOKEN}
        data = {"asset": "USDT", "amount": str(amount_usdt)}
        response = requests.post('https://pay.crypt.bot/api/createInvoice', headers=headers, json=data, timeout=10)
        
        if response.ok:
            response_data = response.json()
            if response_data.get('ok'):
                return response_data['result']['pay_url'], response_data['result']['invoice_id']
            else:
                print(f"Ошибка CryptoPay: {response_data.get('error')}")
                return None, None
        else:
            print(f"HTTP ошибка: {response.status_code}")
            return None, None
    except Exception as e:
        print(f"Ошибка при создании счета: {e}")
        return None, None

def check_payment_status(invoice_id):
    try:
        headers = {
            "Crypto-Pay-API-Token": API_TOKEN,
            "Content-Type": "application/json"
        }
        response = requests.post('https://pay.crypt.bot/api/getInvoices', headers=headers, json={}, timeout=10)
        
        if response.ok:
            return response.json()
        else:
            print(f"Ошибка при запросе к API: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Ошибка при проверке оплаты: {e}")
        return None

user_file_positions = {}
mailing_data = {}
user_states = {}

def main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('🛒 Магазин файлов')
    btn2 = types.KeyboardButton('📤 Продать файл')
    btn3 = types.KeyboardButton('👤 Мой профиль')
    btn4 = types.KeyboardButton('📋 Мои файлы')
    
    user = get_user(chat_id)
    if user and user[1] == ADMIN_ID:
        btn5 = types.KeyboardButton('⚙️ Админ панель')
        markup.add(btn1, btn2, btn3, btn4, btn5)
    else:
        markup.add(btn1, btn2, btn3, btn4)
    
    return markup

def back_button():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton('🔙 Назад')
    markup.add(btn)
    return markup

@bot.message_handler(commands=['start'])
def welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    add_user(user_id, username, first_name, last_name)
    
    markup = main_menu(message.chat.id)
    
    welcome_text = """
🎯 Добро пожаловать в FV shop

➕ Покупайте и продавайте файлы безопасно и удобно
🔔 Вы будете получать уведомления о новых файлах

Выберите действие из меню ниже: ⬇️
    """
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '🗑️ Удалить файл')
def delete_file_prompt(message):
    user_id = message.from_user.id
    
    bot.send_message(message.chat.id, 
                    "📝 Введите точное название файла, который хотите удалить:\n\n"
                    "⚠️ Внимание: файл будет безвозвратно удален из магазина!",
                    reply_markup=back_button())
    
    if user_id not in user_file_positions:
        user_file_positions[user_id] = {}
    user_file_positions[user_id]['waiting_for_delete'] = True
    
    bot.register_next_step_handler(message, process_delete_file)

def process_delete_file(message):
    if message.text == '🔙 Назад':
        markup = main_menu(message.chat.id)
        bot.send_message(message.chat.id, "🔙 Возвращаемся в главное меню:", reply_markup=markup)
        if message.from_user.id in user_file_positions:
            user_file_positions[message.from_user.id]['waiting_for_delete'] = False
        return
    
    user_id = message.from_user.id
    file_name_to_delete = message.text.strip()
    
    file = get_user_file_by_name(user_id, file_name_to_delete)
    
    if not file:
        bot.send_message(message.chat.id, 
                        f"❌ Файл с названием '{file_name_to_delete}' не найден!\n\n"
                        f"Проверьте название и попробуйте снова.",
                        reply_markup=back_button())
        bot.register_next_step_handler(message, process_delete_file)
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_confirm = types.InlineKeyboardButton('✅ Да, удалить', callback_data=f'confirm_delete_{file[0]}')
    btn_cancel = types.InlineKeyboardButton('❌ Отмена', callback_data='cancel_delete')
    markup.add(btn_confirm, btn_cancel)
    
    price_usdt = file[5] / USDT_TO_RUB
    
    bot.send_message(message.chat.id,
                    f"📄 Название: {file[2]}\n"
                    f"💰 Цена: {file[5]:.2f} RUB | {price_usdt:.2f} USDT\n"
                    f"📝 Описание: {file[3][:100]}...\n\n"
                    f"❓ Вы уверены, что хотите удалить этот файл?",
                    reply_markup=markup)
    
    if user_id in user_file_positions:
        user_file_positions[user_id]['waiting_for_delete'] = False

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    if message.text == '🔙 Назад':
        markup = main_menu(message.chat.id)
        bot.send_message(message.chat.id, "🔙 Возвращаемся в главное меню:", reply_markup=markup)
    
    elif message.text == '👤 Мой профиль':
        profile(message)
    
    elif message.text == '📋 Мои файлы':
        my_files(message)
    
    elif message.text == '📤 Продать файл':
        sell_file(message)
    
    elif message.text == '🛒 Магазин файлов':
        buy_file(message)
    
    elif message.text == '⚙️ Админ панель':
        admin_panel(message)
    
    elif message.text == '📊 Статистика' and message.from_user.id == ADMIN_ID:
        admin_stats(message)
    
    elif message.text == '👥 Пользователи' and message.from_user.id == ADMIN_ID:
        admin_users(message)
    
    elif message.text == '💼 Баланс' and message.from_user.id == ADMIN_ID:
        admin_balance(message)
    
    elif message.text == '📢 Рассылка' and message.from_user.id == ADMIN_ID:
        mailing(message)
    
    elif message.text == '🔙 Главное меню' and message.from_user.id == ADMIN_ID:
        back_to_main_from_admin(message)
    
    elif message.text == '🔔 Уведомления' or message.text == '🔕 Уведомления':
        toggle_notifications_menu(message)

def toggle_notifications_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user:
        current_status = user[8] if len(user) > 8 else 1
        
        status_text = "включены 🔔" if current_status else "отключены 🔕"
        
        text = f"🔔 Статус уведомлений: {status_text}\n\n"
        text += "Вы будете получать уведомления о новых файлах в магазине."
        
        markup = types.InlineKeyboardMarkup()
        if current_status:
            btn = types.InlineKeyboardButton('🔕 Отключить уведомления', callback_data='disable_notifications')
        else:
            btn = types.InlineKeyboardButton('🔔 Включить уведомления', callback_data='enable_notifications')
        markup.add(btn)
        
        bot.send_message(message.chat.id, text, reply_markup=markup)

def profile(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user:
        join_date = datetime.strptime(user[6], '%Y-%m-%d %H:%M:%S')
        days_in_bot = (datetime.now() - join_date).days
        
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET days_in_bot = ? WHERE user_id = ?', (days_in_bot, user_id))
        
        cursor.execute('SELECT COUNT(*) FROM files WHERE user_id = ?', (user_id,))
        total_files = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM files WHERE user_id = ? AND is_sold = 1', (user_id,))
        sold_files = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(amount_rub) FROM held_balances WHERE user_id = ? AND released = 0', (user_id,))
        held_amount = cursor.fetchone()[0] or 0
        
        notification_status = "🔔 Включены" if user[8] else "🔕 Отключены"
        
        conn.commit()
        conn.close()
        
        profile_text = f"""
👤 ПРОФИЛЬ

🆔 ID: {user[1]}
🌐 Username: @{user[2] if user[2] else 'Не указан'}
📅 В боте: {days_in_bot} дней
🔔 Уведомления: {notification_status}

💰 Баланс: {user[5]:.2f} RUB
⏳ В ожидании: {held_amount:.2f} RUB

📊 Статистика:
📁 Всего файлов: {total_files}
💼 Продано: {sold_files}
        """
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton('💳 Пополнить', callback_data='deposit')
        btn2 = types.InlineKeyboardButton('💸 Вывести', callback_data='withdraw')
        btn3 = types.InlineKeyboardButton('🔔 Уведомления', callback_data='notifications_settings')
        markup.add(btn1, btn2, btn3)
        
        bot.send_message(message.chat.id, profile_text, reply_markup=markup)

def my_files(message):
    user_id = message.from_user.id
    files = get_user_files(user_id)
    
    if not files:
        bot.send_message(message.chat.id, "📭 У вас нет активных файлов для продажи.")
        return
    
    text = "📁 Ваши файлы в продаже:\n\n"
    for i, file in enumerate(files, 1):
        price_usdt = file[5] / USDT_TO_RUB
        text += f"{i}. 📄 {file[2]}\n"
        text += f"   💰 {file[5]:.2f} RUB | {price_usdt:.2f} USDT\n"
        text += f"   📝 {file[3][:50]}...\n"
        text += f"   🆔 ID: {file[0]}\n\n"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_delete = types.KeyboardButton('🗑️ Удалить файл')
    btn_back = types.KeyboardButton('🔙 Назад')
    markup.add(btn_delete, btn_back)
    
    bot.send_message(message.chat.id, text + "\nЧтобы удалить файл, нажмите кнопку ниже и введите название файла:", reply_markup=markup)
    
    user_file_positions[user_id] = {'files': files, 'waiting_for_delete': False}

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == 'deposit':
        deposit(call)
    elif call.data == 'withdraw':
        withdraw(call)
    elif call.data.startswith('cryptobot_deposit_'):
        cryptobot_deposit(call)
    elif call.data.startswith('check_deposit_'):
        check_deposit(call)
    elif call.data.startswith(('approve_withdraw_', 'reject_withdraw_')):
        handle_withdraw_request(call)
    elif call.data == 'next_file':
        next_file(call)
    elif call.data == 'open_shop':
        open_shop(call)
    elif call.data.startswith('buy_'):
        buy_file_callback(call)
    elif call.data == 'confirm_mailing':
        confirm_mailing(call)
    elif call.data == 'cancel_mailing':
        cancel_mailing(call)
    elif call.data == 'notifications_settings':
        notifications_settings(call)
    elif call.data == 'enable_notifications':
        enable_notifications(call)
    elif call.data == 'disable_notifications':
        disable_notifications(call)
    elif call.data.startswith('confirm_delete_'):
        confirm_delete_file(call)
    elif call.data == 'cancel_delete':
        cancel_delete(call)

def confirm_delete_file(call):
    file_id = int(call.data.split('_')[2])
    
    file = get_file_by_id(file_id)
    
    if not file:
        bot.answer_callback_query(call.id, '❌ Файл не найден!')
        return
    
    if file[1] != call.from_user.id:
        bot.answer_callback_query(call.id, '❌ У вас нет прав для удаления этого файла!')
        return
    
    delete_file(file_id)
    
    bot.answer_callback_query(call.id, '✅ Файл успешно удален!')
    bot.edit_message_text(f"✅ Файл '{file[2]}' успешно удален из магазина!",
                         call.message.chat.id,
                         call.message.message_id)

def cancel_delete(call):
    bot.answer_callback_query(call.id, '❌ Удаление отменено')
    bot.edit_message_text("❌ Удаление файла отменено.",
                         call.message.chat.id,
                         call.message.message_id)

def open_shop(call):
    buy_file(call.message)

def notifications_settings(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    
    if user:
        current_status = user[8] if len(user) > 8 else 1
        
        status_text = "включены 🔔" if current_status else "отключены 🔕"
        
        text = f"🔔 Настройка уведомлений\n\n"
        text += f"Текущий статус: {status_text}\n\n"
        text += "При включенных уведомлениях вы будете получать оповещения о новых файлах в магазине."
        
        markup = types.InlineKeyboardMarkup()
        if current_status:
            btn = types.InlineKeyboardButton('🔕 Отключить', callback_data='disable_notifications')
        else:
            btn = types.InlineKeyboardButton('🔔 Включить', callback_data='enable_notifications')
        markup.add(btn)
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

def enable_notifications(call):
    user_id = call.from_user.id
    new_status = toggle_notifications(user_id)
    
    bot.answer_callback_query(call.id, '✅ Уведомления включены!')
    bot.edit_message_text("🔔 Уведомления успешно включены!\n\nТеперь вы будете получать оповещения о новых файлах.",
                         call.message.chat.id,
                         call.message.message_id)

def disable_notifications(call):
    user_id = call.from_user.id
    new_status = toggle_notifications(user_id)
    
    bot.answer_callback_query(call.id, '🔕 Уведомления отключены')
    bot.edit_message_text("🔕 Уведомления отключены.\n\nВы больше не будете получать оповещения о новых файлах.",
                         call.message.chat.id,
                         call.message.message_id)

def deposit(call):
    bot.edit_message_text(f"💵 Введите сумму пополнения в RUB:\n\n"
                         f"⚠️ Минимальная сумма: {MIN_DEPOSIT_AMOUNT} RUB\n",
                         call.message.chat.id,
                         call.message.message_id)
    
    user_states[call.from_user.id] = 'waiting_deposit_amount'
    bot.register_next_step_handler(call.message, process_deposit_amount)

def process_deposit_amount(message):
    if message.text == '🔙 Назад':
        markup = main_menu(message.chat.id)
        bot.send_message(message.chat.id, "🔙 Возвращаемся в главное меню:", reply_markup=markup)
        if message.from_user.id in user_states:
            del user_states[message.from_user.id]
        return
        
    try:
        amount_rub = float(message.text)
        
        if amount_rub < MIN_DEPOSIT_AMOUNT:
            bot.send_message(message.chat.id, 
                           f"❌ Минимальная сумма пополнения - {MIN_DEPOSIT_AMOUNT} RUB!",
                           reply_markup=back_button())
            return
            
        amount_usdt = amount_rub / USDT_TO_RUB
        
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton('💳 CryptoBot', callback_data=f'cryptobot_deposit_{amount_usdt:.2f}_{amount_rub:.2f}')
        markup.add(btn)
        
        bot.send_message(message.chat.id, 
                        f"💵 Выберите способ пополнения:\n\n"
                        f"🏦 Пополнить другим способом? Легко! Админ ждет вас тут: @famelonov 😊\n\n"
                        f"Сумма к оплате: {amount_rub:.2f} RUB\n",
                        reply_markup=markup)
        
        if message.from_user.id in user_states:
            del user_states[message.from_user.id]
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректную сумму!", reply_markup=back_button())

def cryptobot_deposit(call):
    data = call.data.split('_')
    amount_usdt = float(data[2])
    amount_rub = float(data[3])
    
    pay_link, invoice_id = get_pay_link(amount_usdt)
    
    if pay_link and invoice_id:
        add_transaction(call.from_user.id, amount_rub, amount_usdt, 'deposit', 'pending', invoice_id)
        
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('💳 Оплатить', url=pay_link)
        btn2 = types.InlineKeyboardButton('🔄 Проверить оплату', callback_data=f'check_deposit_{invoice_id}')
        markup.add(btn1, btn2)
        
        bot.edit_message_text(f"💳 Для пополнения баланса на {amount_rub:.2f} RUB\n"
                             f"Необходимо оплатить {amount_usdt:.2f} USDT\n\n"
                             f"Перейдите по ссылке для оплаты:",
                             call.message.chat.id,
                             call.message.message_id,
                             reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, '❌ Ошибка при создании счета! Попробуйте позже.')

def check_deposit(call):
    invoice_id = call.data.split('check_deposit_')[1]
    payment_status = check_payment_status(invoice_id)
    
    if payment_status and payment_status.get('ok'):
        invoice = next((inv for inv in payment_status['result']['items'] if str(inv['invoice_id']) == invoice_id), None)
        if invoice and invoice['status'] == 'paid':
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute('SELECT amount_rub, amount_usdt FROM transactions WHERE invoice_id = ?', (invoice_id,))
            transaction = cursor.fetchone()
            conn.close()
            
            if transaction:
                amount_rub = transaction[0]
                amount_usdt = transaction[1]
                
                commission = amount_rub * DEPOSIT_COMMISSION
                net_amount = amount_rub * (1 - DEPOSIT_COMMISSION)
                
                update_balance_rub(call.from_user.id, net_amount)
                update_balance_rub(ADMIN_ID, commission)
                
                complete_transaction(invoice_id)
                
                bot.edit_message_text(f"✅ Оплата прошла успешно!\n\n"
                                    f"💰 Зачислено: {net_amount:.2f} RUB\n"
                                    f"⚡ Комиссия: {commission:.2f} RUB",
                                    call.message.chat.id,
                                    call.message.message_id)
            else:
                bot.answer_callback_query(call.id, '❌ Транзакция не найдена!')
        else:
            bot.answer_callback_query(call.id, '❌ Оплата не найдена!')
    else:
        bot.answer_callback_query(call.id, '❌ Ошибка при проверке оплаты!')

def withdraw(call):
    bot.edit_message_text("💸 Введите сумму для вывода в RUB:\n\n"
                         "⚠️ Минимальная сумма: 75 RUB",
                         call.message.chat.id,
                         call.message.message_id)
    
    user_states[call.from_user.id] = 'waiting_withdraw_amount'
    bot.register_next_step_handler(call.message, process_withdraw_amount)

def process_withdraw_amount(message):
    if message.text == '🔙 Назад':
        markup = main_menu(message.chat.id)
        bot.send_message(message.chat.id, "🔙 Возвращаемся в главное меню:", reply_markup=markup)
        if message.from_user.id in user_states:
            del user_states[message.from_user.id]
        return
        
    try:
        amount_rub = float(message.text)
        user = get_user(message.from_user.id)
        
        min_amount_rub = USDT_TO_RUB
        
        if amount_rub < min_amount_rub:
            bot.send_message(message.chat.id, f"❌ Минимальная сумма вывода - {min_amount_rub} RUB!", reply_markup=back_button())
            return
        
        if user[5] < amount_rub:
            bot.send_message(message.chat.id, "❌ Недостаточно средств на балансе!", reply_markup=back_button())
            return
            
        update_balance_rub(message.from_user.id, -amount_rub)
        
        bot.send_message(message.chat.id, "🔗 Отправьте ссылку на ваш счет USDT (CryptoBot):", 
                        reply_markup=back_button())
        bot.register_next_step_handler(message, process_withdraw_address, amount_rub)
        
        if message.from_user.id in user_states:
            del user_states[message.from_user.id]
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректную сумму!", reply_markup=back_button())

def process_withdraw_address(message, amount_rub):
    if message.text == '🔙 Назад':
        markup = main_menu(message.chat.id)
        bot.send_message(message.chat.id, "🔙 Возвращаемся в главное меню:", reply_markup=markup)
        return
        
    address = message.text
    user_id = message.from_user.id
    amount_usdt = amount_rub / USDT_TO_RUB
    
    admin_text = f"📋 НОВАЯ ЗАЯВКА НА ВЫВОД\n\n"
    admin_text += f"👤 Пользователь: @{message.from_user.username if message.from_user.username else 'Нет username'}\n"
    admin_text += f"🆔 ID: {user_id}\n"
    admin_text += f"💶 Сумма: {amount_rub:.2f} RUB\n"
    admin_text += f"💵 В USDT: {amount_usdt:.2f} USDT\n"
    admin_text += f"🔗 Счет: {address}\n"
    admin_text += f"💰 Баланс: {get_user(user_id)[5]:.2f} RUB"
    
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('✅ Одобрить', callback_data=f'approve_withdraw_{user_id}_{amount_rub}')
    btn2 = types.InlineKeyboardButton('❌ Отменить', callback_data=f'reject_withdraw_{user_id}_{amount_rub}')
    markup.add(btn1, btn2)
    
    bot.send_message(ADMIN_ID, admin_text, reply_markup=markup)
    
    bot.send_message(message.chat.id, 
                    "✅ Заявка на вывод отправлена!\n"
                    "⏰ Ожидайте обработки администратором.",
                    reply_markup=main_menu(message.chat.id))

def handle_withdraw_request(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, '❌ У вас нет прав для этого действия!')
        return
        
    data = call.data.split('_')
    action = data[0]
    user_id = int(data[2])
    amount_rub = float(data[3])
    amount_usdt = amount_rub / USDT_TO_RUB
    
    if action == 'approve':
        bot.send_message(user_id, 
                        f"✅ Ваша заявка на вывод одобрена!\n"
                        f"💰 Сумма: {amount_rub:.2f} RUB | {amount_usdt:.2f} USDT\n")
        bot.edit_message_text(f"⏰ Средства будут переведены в ближайшее время.\n",
                            call.message.chat.id,
                            call.message.message_id)
    else:
        update_balance_rub(user_id, amount_rub)
        bot.send_message(user_id, 
                        f"❌ Ваша заявка на вывод отклонена.\n"
                        f"💰 Средства {amount_rub:.2f} RUB возвращены на баланс.")
        bot.edit_message_text(f"❌ Вывод для пользователя {user_id} отклонен.\n"
                            f"💰 Сумма: {amount_rub:.2f} RUB",
                            call.message.chat.id,
                            call.message.message_id)

def sell_file(message):
    bot.send_message(message.chat.id, 
                    "📤 Отправьте файл, который хотите продать:\n\n"
                    "📌 Разрешенные форматы: .py, .zip, .rar, .js\n"
                    "⚠️ Максимальный размер: 50 MB",
                    reply_markup=back_button())
    bot.register_next_step_handler(message, process_file)

def process_file(message):
    if message.text == '🔙 Назад':
        markup = main_menu(message.chat.id)
        bot.send_message(message.chat.id, "🔙 Возвращаемся в главное меню:", reply_markup=markup)
        return
        
    if not message.document:
        bot.send_message(message.chat.id, 
                        "❌ Ошибка! Пожалуйста, отправьте файл.\n"
                        "📌 Разрешенные форматы: .py, .zip, .rar, .js",
                        reply_markup=back_button())
        return
        
    file_id = message.document.file_id
    file_name = message.document.file_name
    
    allowed_extensions = ('.py', '.zip', '.rar', '.js')
    if not file_name.lower().endswith(allowed_extensions):
        bot.send_message(message.chat.id, 
                        "❌ Неподдерживаемый формат файла!\n"
                        "📌 Разрешены только: .py, .zip, .rar, .js",
                        reply_markup=back_button())
        return
    
    user_file_positions[message.from_user.id] = {'file_id': file_id, 'file_name': file_name}
    
    bot.send_message(message.chat.id, 
                    "📝 Теперь напишите описание для файла:\n\n"
                    "Расскажите подробнее о том, что продаете",
                    reply_markup=back_button())
    bot.register_next_step_handler(message, process_description)

def process_description(message):
    if message.text == '🔙 Назад':
        markup = main_menu(message.chat.id)
        bot.send_message(message.chat.id, "🔙 Возвращаемся в главное меню:", reply_markup=markup)
        return
    
    description = message.text
    
    file_info = user_file_positions.get(message.from_user.id, {})
    file_id = file_info.get('file_id')
    file_name = file_info.get('file_name')
    
    if not file_id or not file_name:
        bot.send_message(message.chat.id, "❌ Ошибка! Начните процесс заново.", reply_markup=main_menu(message.chat.id))
        return
    
    user_file_positions[message.from_user.id]['description'] = description
    
    bot.send_message(message.chat.id, 
                    "💰 Укажите цену в RUB:\n\n"
                    f"⚠️ Минимальная цена: {MIN_SELL_PRICE} RUB",
                    reply_markup=back_button())
    bot.register_next_step_handler(message, process_price, file_id, file_name, description)

def process_price(message, file_id, file_name, description):
    if message.text == '🔙 Назад':
        markup = main_menu(message.chat.id)
        bot.send_message(message.chat.id, "🔙 Возвращаемся в главное меню:", reply_markup=markup)
        return
        
    try:
        price_rub = float(message.text)
        if price_rub < MIN_SELL_PRICE:
            bot.send_message(message.chat.id, f"❌ Минимальная цена - {MIN_SELL_PRICE} RUB!", reply_markup=back_button())
            return
            
        file_db_id = add_file(message.from_user.id, file_name, description, file_id, price_rub)
        
        if message.from_user.id in user_file_positions:
            del user_file_positions[message.from_user.id]
        
        price_usdt = price_rub / USDT_TO_RUB
        
        success_text = f"""
✅ Файл успешно добавлен в магазин!

📁 Название: {file_name}
💰 Цена: {price_rub:.2f} RUB | {price_usdt:.2f} USDT
📝 Описание: {description[:100]}...

🔔 Уведомления о новом файле будут отправлены всем пользователям!
⏰ Ожидайте покупателей!
        """
        
        bot.send_message(message.chat.id, success_text, reply_markup=main_menu(message.chat.id))
        
        threading.Thread(target=notify_users_about_new_file, args=(file_db_id,), daemon=True).start()
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректную цену!", reply_markup=back_button())

def buy_file(message):
    files = get_all_files()
    
    if not files:
        bot.send_message(message.chat.id, 
                        "📭 Магазин пуст\n\n"
                        "На данный момент нет доступных файлов для покупки.\n"
                        "Попробуйте зайти позже!")
        return
        
    user_file_positions[message.from_user.id] = {'position': 0, 'total_files': len(files)}
    show_file(message.chat.id, message.from_user.id, 0)

def show_file(chat_id, user_id, position):
    files = get_all_files()
    
    if position >= len(files):
        bot.send_message(chat_id, "📭 Больше нет файлов для показа.")
        return
        
    file = files[position]
    
    price_usdt = file[5] / USDT_TO_RUB
    
    caption = f"""
📁 ФАЙЛ #{position + 1}

📄 Название: {file[2]}

📝 Описание: 
{file[3]}

💰 Цена: 
💶 {file[5]:.2f} RUB
💵 {price_usdt:.2f} USDT

📊 Прогресс: {position + 1}/{len(files)}
    """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🛒 Купить', callback_data=f'buy_{file[0]}')
    btn2 = types.InlineKeyboardButton('➡️ Следующий', callback_data='next_file')
    markup.add(btn1, btn2)
    
    bot.send_message(chat_id, caption, reply_markup=markup)
    user_file_positions[user_id] = {'position': position, 'total_files': len(files)}

def next_file(call):
    user_id = call.from_user.id
    current_position = user_file_positions.get(user_id, {'position': 0})['position']
    show_file(call.message.chat.id, user_id, current_position + 1)
    bot.delete_message(call.message.chat.id, call.message.message_id)

def buy_file_callback(call):
    file_id = int(call.data.split('_')[1])
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM files WHERE id = ?', (file_id,))
    file = cursor.fetchone()
    conn.close()
    
    if not file:
        bot.answer_callback_query(call.id, '❌ Файл не найден!')
        return
        
    user = get_user(call.from_user.id)
    
    if user[5] < file[5]:
        bot.answer_callback_query(call.id, '❌ Недостаточно средств на балансе!')
        return
        
    commission = file[5] * SALE_COMMISSION
    seller_amount = file[5] * (1 - SALE_COMMISSION)
    
    update_balance_rub(call.from_user.id, -file[5])
    
    hold_until = add_held_balance(file[1], file_id, seller_amount)
    
    update_balance_rub(ADMIN_ID, commission)
    
    mark_file_sold(file_id, call.from_user.id)
    
    user_id = call.from_user.id
    position = user_file_positions.get(user_id, {'position': 0})['position']
    total_files = user_file_positions.get(user_id, {'total_files': 1})['total_files']
    
    try:
        price_usdt = file[5] / USDT_TO_RUB
        bot.send_document(call.from_user.id, file[4], 
                         caption=f"📁 {file[2]}\n\n"
                                f"📝 Описание: {file[3]}2\n"
                                f"💰 Цена: {file[5]:.2f} RUB | {price_usdt:.2f} USDT\n\n"
                                f"📊 Файл {position + 1} из {total_files}")
    except Exception as e:
        bot.send_message(call.from_user.id, f"❌ Ошибка при отправке файла: {str(e)}")
        bot.answer_callback_query(call.id, '❌ Ошибка при отправке файла!')
        return
    
    seller_amount_usdt = seller_amount / USDT_TO_RUB
    commission_usdt = commission / USDT_TO_RUB
    
    hold_time_str = datetime.strptime(hold_until, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
    
    bot.send_message(file[1], 
                    f"🎉 Ваш файл был продан!\n\n"
                    f"📁 Файл: {file[2]}\n"
                    f"💰 Вы получите: {seller_amount:.2f} RUB | {seller_amount_usdt:.2f} USDT\n"
                    f"⚡ Комиссия системы: {commission:.2f} RUB | {commission_usdt:.2f} USDT\n"
                    f"⏰ Средства поступят на баланс через {HOLDING_HOURS} час(ов)\n")
    
    bot.answer_callback_query(call.id, '✅ Файл успешно приобретен!')
    bot.delete_message(call.message.chat.id, call.message.message_id)

def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет доступа к админ панели!")
        return
        
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('📊 Статистика')
    btn2 = types.KeyboardButton('👥 Пользователи')
    btn3 = types.KeyboardButton('💼 Баланс')
    btn4 = types.KeyboardButton('📢 Рассылка')
    btn5 = types.KeyboardButton('🔙 Главное меню')
    markup.add(btn1, btn2, btn3, btn4, btn5)
    
    bot.send_message(message.chat.id, "⚙️ Админ панель:", reply_markup=markup)

def mailing(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    bot.send_message(message.chat.id, 
                    "📢 Введите пост для рассылки:\n\n"
                    "Доступно: текст\n"
                    "⚠️ Фото и видео временно отключены для избежания ошибок",
                    reply_markup=back_button())
    
    mailing_data[message.from_user.id] = {'step': 'waiting_content'}
    bot.register_next_step_handler(message, process_mailing_content)

def process_mailing_content(message):
    if message.text == '🔙 Назад':
        admin_panel(message)
        return
    
    admin_id = message.from_user.id
    
    if message.content_type != 'text':
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте только текстовое сообщение для рассылки.", reply_markup=back_button())
        bot.register_next_step_handler(message, process_mailing_content)
        return
    
    mailing_data[admin_id] = {
        'content_type': 'text',
        'text': message.text
    }
    
    users = get_all_users()
    total_users = len(users)
    
    if total_users == 0:
        bot.send_message(message.chat.id, "❌ Нет пользователей для рассылки!")
        return
    
    markup = types.InlineKeyboardMarkup()
    btn_confirm = types.InlineKeyboardButton('✅ Подтвердить', callback_data='confirm_mailing')
    btn_cancel = types.InlineKeyboardButton('❌ Отмена', callback_data='cancel_mailing')
    markup.add(btn_confirm, btn_cancel)
    
    bot.send_message(message.chat.id, 
                    f"📊 Будет отправлено {total_users} пользователям\n\n"
                    f"Текст сообщения:\n{message.text[:100]}...\n\n"
                    f"Подтвердите рассылку:",
                    reply_markup=markup)

def confirm_mailing(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    admin_id = call.from_user.id
    mailing_info = mailing_data.get(admin_id)
    
    if not mailing_info:
        bot.answer_callback_query(call.id, '❌ Данные рассылки не найдены!')
        return
    
    users = get_all_users()
    sent_count = 0
    failed_count = 0
    
    bot.edit_message_text("📢 Рассылка началась...",
                         call.message.chat.id,
                         call.message.message_id)
    
    for user_id, _ in users:
        try:
            if mailing_info['content_type'] == 'text':
                bot.send_message(user_id, mailing_info['text'])
            
            sent_count += 1
            time.sleep(0.05)
            
        except Exception as e:
            failed_count += 1
            print(f"Ошибка отправки пользователю {user_id}: {e}")
    
    add_mailing_record(admin_id, mailing_info['content_type'], 0, sent_count)
    
    bot.send_message(call.message.chat.id,
                    f"✅ Рассылка завершена!\n\n"
                    f"📊 Отправлено: {sent_count}\n"
                    f"❌ Не удалось: {failed_count}")
    
    if admin_id in mailing_data:
        del mailing_data[admin_id]

def cancel_mailing(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    admin_id = call.from_user.id
    if admin_id in mailing_data:
        del mailing_data[admin_id]
    
    bot.edit_message_text("❌ Рассылка отменена",
                         call.message.chat.id,
                         call.message.message_id)

def admin_stats(message):
    if message.from_user.id != ADMIN_ID:
        return
        
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM files')
    total_files = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM files WHERE is_sold = 1')
    sold_files = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(balance_rub) FROM users')
    total_balance = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(amount_rub) FROM held_balances WHERE released = 0')
    total_held = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE notification_enabled = 1')
    notifications_on = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE notification_enabled = 0')
    notifications_off = cursor.fetchone()[0]
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM users WHERE join_date LIKE ?', (f'{today}%',))
    new_users_today = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM files WHERE sold_at LIKE ?', (f'{today}%',))
    sales_today = cursor.fetchone()[0]
    
    conn.close()
    
    total_balance_usdt = total_balance / USDT_TO_RUB
    total_held_usdt = total_held / USDT_TO_RUB
    
    stats_text = f"""
📊 СТАТИСТИКА

👥 Всего пользователей: {total_users}
📈 Новых сегодня: {new_users_today}
🔔 Уведомления вкл: {notifications_on}
🔕 Уведомления выкл: {notifications_off}

📁 Всего файлов: {total_files}
💼 Продано файлов: {sold_files}
📊 Продаж сегодня: {sales_today}

💰 Общий баланс: 
💶 {total_balance:.2f} RUB   
💵 {total_balance_usdt:.2f} USDT

⏳ В удержании: 
💶 {total_held:.2f} RUB
💵 {total_held_usdt:.2f} USDT
    """
    
    bot.send_message(message.chat.id, stats_text)

def admin_users(message):
    if message.from_user.id != ADMIN_ID:
        return
        
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, balance_rub, notification_enabled FROM users ORDER BY id DESC LIMIT 10')
    users = cursor.fetchall()
    conn.close()
    
    users_text = "👥 Последние 10 пользователей:\n\n"
    for user in users:
        balance_usdt = user[2] / USDT_TO_RUB
        notification_icon = "🔔" if user[3] else "🔕"
        users_text += f"{notification_icon} 🆔 {user[0]} | @{user[1] or 'Нет username'} | 💶 {user[2]:.2f} RUB | 💵 {balance_usdt:.2f} USDT\n"
    
    bot.send_message(message.chat.id, users_text)

def admin_balance(message):
    if message.from_user.id != ADMIN_ID:
        return
        
    bot.send_message(message.chat.id, "💼 Введите ID пользователя для изменения баланса:", 
                    reply_markup=back_button())
    bot.register_next_step_handler(message, process_user_id_for_balance)

def process_user_id_for_balance(message):
    if message.text == '🔙 Назад':
        admin_panel(message)
        return
        
    try:
        user_id = int(message.text)
        user = get_user(user_id)
        
        if not user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден!", reply_markup=back_button())
            return
            
        balance_usdt = user[5] / USDT_TO_RUB
        
        bot.send_message(message.chat.id, 
                        f"👤 Пользователь: @{user[2] or 'Нет username'}\n"
                        f"💰 Текущий баланс: {user[5]:.2f} RUB | {balance_usdt:.2f} USDT\n\n"
                        f"💼 Введите новую сумму баланса в RUB:",
                        reply_markup=back_button())
        bot.register_next_step_handler(message, process_new_balance, user_id)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректный ID!", reply_markup=back_button())

def process_new_balance(message, user_id):
    if message.text == '🔙 Назад':
        admin_panel(message)
        return
        
    try:
        new_balance_rub = float(message.text)
        set_balance_rub(user_id, new_balance_rub)
        
        new_balance_usdt = new_balance_rub / USDT_TO_RUB
        
        bot.send_message(message.chat.id, 
                        f"✅ Баланс пользователя {user_id} изменен!\n"
                        f"💰 Новый баланс: {new_balance_rub:.2f} RUB | {new_balance_usdt:.2f} USDT")
        admin_panel(message)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректную сумму!", reply_markup=back_button())

def back_to_main_from_admin(message):
    markup = main_menu(message.chat.id)
    bot.send_message(message.chat.id, "🔙 Возвращаемся в главное меню:", reply_markup=markup)

def check_held_balances():
    while True:
        try:
            released = release_held_balances()
            if released > 0:
                print(f"Освобождено {released} удержаний")
            time.sleep(60)
        except Exception as e:
            print(f"Ошибка при освобождении удержаний: {e}")
            time.sleep(60)

if __name__ == '__main__':
    print("Бот запущен...")
    
    threading.Thread(target=check_held_balances, daemon=True).start()
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Ошибка при запуске бота: {e}")

            time.sleep(5)

