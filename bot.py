import telebot
import requests
import time
from datetime import datetime
import threading
import json
import os

TOKEN = "8134986426:AAF_Np2hSvspbrBfcsjsr9Szd77yb0WiIBI"
bot = telebot.TeleBot(TOKEN)

# Admin ID ro'yxati (o'zingizning IDngizni qo'shing)
ADMIN_IDS = [7399101034 ]  # SIZNING TELEGRAM IDINGIZNI YOZING

interval = 5

coins = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "SOL": "SOLUSDT",
    "LTC": "LTCUSDT",
    "TON": "TONUSDT",
    "TRX": "TRXUSDT",
    "DOGE": "DOGEUSDT"
}

emoji_id = {
    "BTC": "5215277894456089919",
    "ETH": "5215469686220688535",
    "BNB": "5215501052366852398",
    "SOL": "5215644439850028163",
    "LTC": "5215397251597243962",
    "TON": "5215541953340410399",
    "TRX": "5215676493190960888",
    "DOGE": "5215580724010193095"
}

user_messages = {}  # chat_id: message_id
all_users = set()   # Barcha foydalanuvchilar ro'yxati

# Foydalanuvchilarni saqlash
def save_users():
    with open("users.json", "w") as f:
        json.dump(list(all_users), f)

def load_users():
    global all_users
    if os.path.exists("users.json"):
        with open("users.json", "r") as f:
            all_users = set(json.load(f))

def get_prices():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=5)
        data = r.json()
        prices = {}
        for item in data:
            for coin, symbol in coins.items():
                if item["symbol"] == symbol:
                    prices[coin] = float(item["price"])
        return prices
    except:
        return {}

def build_message(prices):
    t = datetime.now().strftime("%H:%M:%S")
    text = "<b>💰 AlphaCryptoPrice PRO</b>\n\n"
    for coin in coins:
        price = prices.get(coin, 0)
        icon = f"<tg-emoji emoji-id='{emoji_id[coin]}'>🙂</tg-emoji>"
        text += f"{icon} {coin} | ${price:,.2f} | {t}\n\n"
    text += f"🔄 Auto Update: {interval} sec\n"
    text += f"👥 Users: {len(all_users)}"
    return text

# Broadcast funksiyasi
def broadcast_message(text, parse_mode="HTML"):
    success = 0
    fail = 0
    for user_id in all_users:
        try:
            bot.send_message(user_id, text, parse_mode=parse_mode)
            success += 1
            time.sleep(0.05)  # Rate limit uchun
        except:
            fail += 1
    return success, fail

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    all_users.add(chat_id)
    save_users()
    
    prices = get_prices()
    msg = build_message(prices)
    sent = bot.send_message(chat_id, msg, parse_mode="HTML")
    user_messages[chat_id] = sent.message_id

    def updater():
        while True:
            prices = get_prices()
            msg = build_message(prices)
            try:
                bot.edit_message_text(msg, chat_id, user_messages[chat_id], parse_mode="HTML")
            except:
                pass
            time.sleep(interval)

    threading.Thread(target=updater, daemon=True).start()

# ADMIN COMMANDS
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ Siz admin emassiz!")
        return
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("📢 Broadcast", callback_data="broadcast"))
    markup.add(telebot.types.InlineKeyboardButton("👥 Users stat", callback_data="stats_users"))
    markup.add(telebot.types.InlineKeyboardButton("🔄 Change interval", callback_data="interval"))
    markup.add(telebot.types.InlineKeyboardButton("📊 Bot status", callback_data="bot_status"))
    
    bot.send_message(message.chat.id, "🔐 <b>Admin Panel</b>", parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['broadcast'])
def broadcast_start(message):
    if message.chat.id not in ADMIN_IDS:
        return
    bot.reply_to(message, "📢 <b>Broadcast xabarini yuboring:</b>\n\n(Ha yoki Yo'q deb javob berish shart emas)", parse_mode="HTML")
    bot.register_next_step_handler(message, send_broadcast)

def send_broadcast(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    msg_text = message.text
    confirm_msg = bot.send_message(message.chat.id, f"⚠️ <b>{len(all_users)} foydalanuvchiga</b> quyidagi xabar yuborilsinmi?\n\n{msg_text}\n\n✅ Ha yuborish uchun /confirm\n❌ Bekor qilish uchun /cancel", parse_mode="HTML")
    
    def confirm_handler(m):
        if m.text == "/confirm":
            success, fail = broadcast_message(msg_text)
            bot.send_message(message.chat.id, f"✅ Broadcast tugadi!\n✓ Yuborildi: {success}\n✗ Xatolik: {fail}")
        else:
            bot.send_message(message.chat.id, "❌ Broadcast bekor qilindi")
    
    bot.register_next_step_handler(confirm_msg, confirm_handler)

@bot.callback_query_handler(func=lambda call: True)
def admin_callback(call):
    if call.message.chat.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ Admin emassiz!")
        return
    
    if call.data == "broadcast":
        bot.answer_callback_query(call.id)
        broadcast_start(call.message)
    
    elif call.data == "stats_users":
        bot.answer_callback_query(call.id)
        text = f"👥 <b>Foydalanuvchilar statistikasi</b>\n\n"
        text += f"Jami userlar: {len(all_users)}\n"
        text += f"Faol chatlar: {len(user_messages)}\n"
        text += f"Adminlar: {len(ADMIN_IDS)}"
        bot.send_message(call.message.chat.id, text, parse_mode="HTML")
    
    elif call.data == "interval":
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("3 sekund", callback_data="set_int_3"))
        markup.add(telebot.types.InlineKeyboardButton("5 sekund", callback_data="set_int_5"))
        markup.add(telebot.types.InlineKeyboardButton("10 sekund", callback_data="set_int_10"))
        bot.edit_message_text("⏱️ Yangilanish intervalini tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data.startswith("set_int_"):
        global interval
        interval = int(call.data.split("_")[2])
        bot.answer_callback_query(call.id, f"✅ Interval {interval} sekundga o'zgartirildi")
        bot.edit_message_text(f"✅ Interval {interval} sekund", call.message.chat.id, call.message.message_id)
    
    elif call.data == "bot_status":
        prices = get_prices()
        text = f"📊 <b>Bot Status</b>\n\n"
        text += f"🟢 Bot ishlayapti\n"
        text += f"⏱️ Interval: {interval}s\n"
        text += f"👥 Users: {len(all_users)}\n"
        text += f"🪙 Coins: {len(coins)}\n"
        text += f"💵 BTC: ${prices.get('BTC', 0):,.0f}"
        bot.send_message(call.message.chat.id, text, parse_mode="HTML")

# Load users on start
load_users()
bot.infinity_polling()
