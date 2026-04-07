import telebot
import requests
import threading
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8134986426:AAF_Np2hSvspbrBfcsjsr9Szd77yb0WiIBI"
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ---------------- COINS ----------------
coins = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "LTC": "litecoin",
    "TON": "the-open-network",
    "TRX": "tron",
    "DOGE": "dogecoin"
}

# ---------------- EMOJI IDS (SENIKI) ----------------
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

users = {}

# ---------------- API ----------------
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
        for c, cid in coins.items():
            if cid in data:
                result[c] = data[cid]["usd"]
        return result
    except:
        return {}

# ---------------- FORMAT ----------------
def fmt(c):
    return f"<tg-emoji emoji-id='{emoji_id[c]}'>🪙</tg-emoji> <b>{c}</b>"

def build(prices, interval):
    text = "<b>📊 PRO Crypto Dashboard</b>\n\n"

    for c, p in prices.items():
        text += f"{fmt(c)} <code>${p:.2f}</code>\n"

    text += f"\n⚙️ Refresh interval: <b>{interval}s</b>"
    return text

# ---------------- PANEL ----------------
def panel(interval):
    kb = InlineKeyboardMarkup()

    kb.row(
        InlineKeyboardButton("➖", callback_data="minus"),
        InlineKeyboardButton(f"⏱ {interval}s", callback_data="none"),
        InlineKeyboardButton("➕", callback_data="plus"),
    )

    kb.row(
        InlineKeyboardButton("🔄 Reset", callback_data="reset")
    )

    return kb

# ---------------- LOOP ----------------
def updater(chat_id):
    while chat_id in users:
        try:
            u = users[chat_id]

            prices = get_prices()

            bot.edit_message_text(
                build(prices, u["interval"]),
                chat_id,
                u["msg_id"],
                reply_markup=panel(u["interval"])
            )

        except:
            pass

        time.sleep(u["interval"])

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(m):
    prices = get_prices()

    msg = bot.send_message(
        m.chat.id,
        build(prices, 5),
        reply_markup=panel(5)
    )

    users[m.chat.id] = {
        "msg_id": msg.message_id,
        "interval": 5
    }

    threading.Thread(target=updater, args=(m.chat.id,), daemon=True).start()

# ---------------- CALLBACK ----------------
@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    uid = call.message.chat.id
    u = users.get(uid)

    if not u:
        return

    if call.data == "plus":
        u["interval"] += 1

    elif call.data == "minus":
        if u["interval"] > 1:
            u["interval"] -= 1

    elif call.data == "reset":
        u["interval"] = 5

    try:
        bot.answer_callback_query(call.id, "⚡ Updated")
    except:
        pass

    try:
        prices = get_prices()

        bot.edit_message_text(
            build(prices, u["interval"]),
            uid,
            u["msg_id"],
            reply_markup=panel(u["interval"])
        )
    except:
        pass

# ---------------- RUN ----------------
bot.infinity_polling()
