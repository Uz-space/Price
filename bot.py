import telebot
import requests
import time
import threading
from datetime import datetime
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8134986426:AAF_Np2hSvspbrBfcsjsr9Szd77yb0WiIBI"
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

coins = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "LTC": "litecoin",
    "TRX": "tron",
    "DOGE": "dogecoin",
}

emoji_id = {
    "BTC": "5215277894456089919",
    "ETH": "5215469686220688535",
    "BNB": "5215501052366852398",
    "SOL": "5215644439850028163",
    "LTC": "5215397251597243962",
    "TRX": "5215676493190960888",
    "DOGE": "5215580724010193095",
}

users = {}

# ---------------- MENU ----------------
def menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("💰 Narxlar"), KeyboardButton("📊 Statistika"))
    kb.add(KeyboardButton("⚙️ Sozlamalar"))
    return kb

# ---------------- API (NO 24HR) ----------------
def get_prices():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": ",".join(coins.values()),
                "vs_currencies": "usd"
            },
            timeout=5
        )
        data = r.json()

        result = {}
        for c, coin_id in coins.items():
            if coin_id in data:
                result[c] = {
                    "price": data[coin_id]["usd"]
                }
        return result

    except Exception as e:
        print("API ERROR:", e)
        return {}

# ---------------- FORMAT ----------------
def fmt(c):
    return f"<tg-emoji emoji-id='{emoji_id[c]}'>🪙</tg-emoji> <b>{c}</b>"

def build(prices):
    t = datetime.now().strftime("%H:%M:%S")
    text = "<b>💰 Kripto Narxlar</b>\n\n"

    for c, i in prices.items():
        text += f"{fmt(c)} <code>${i['price']:.2f}</code>\n"

    text += f"\n🕐 {t}"
    return text

def stats(prices):
    text = "<b>📊 Statistika</b>\n\n"
    for c, i in prices.items():
        text += f"{fmt(c)}\n💵 ${i['price']:.2f}\n\n"
    return text

# ---------------- UPDATER ----------------
def updater(chat_id):
    while chat_id in users:
        if users[chat_id]["section"] == "prices":
            prices = get_prices()
            if prices:
                try:
                    bot.edit_message_text(
                        build(prices),
                        chat_id,
                        users[chat_id]["msg_id"]
                    )
                except:
                    pass
        time.sleep(10)

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(m):
    prices = get_prices()

    msg = bot.send_message(
        m.chat.id,
        build(prices),
        reply_markup=menu()
    )

    users[m.chat.id] = {
        "msg_id": msg.message_id,
        "section": "prices"
    }

    threading.Thread(target=updater, args=(m.chat.id,), daemon=True).start()

# ---------------- MENU ----------------
@bot.message_handler(func=lambda m: m.text == "💰 Narxlar")
def p(m):
    users[m.chat.id]["section"] = "prices"
    bot.send_message(m.chat.id, "📡 Live ON")

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def s(m):
    prices = get_prices()
    bot.send_message(m.chat.id, stats(prices))

@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar")
def settings(m):
    bot.send_message(m.chat.id,
        "⚙️ Sozlamalar:\n"
        "• 💰 Narxlar\n"
        "• 📊 Statistika\n"
        "• /start restart"
    )

# ---------------- RUN ----------------
bot.infinity_polling()
