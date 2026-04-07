import telebot
import requests
import time
from datetime import datetime
import threading

# ═══════════════════════════════════════════
#  SOZLAMALAR
# ═══════════════════════════════════════════
TOKEN = "8134986426:AAF_Np2hSvspbrBfcsjsr9Szd77yb0WiIBI"
DEFAULT_INTERVAL = 10

bot = telebot.TeleBot(TOKEN)

# ═══════════════════════════════════════════
#  KRIPTO MA'LUMOTLARI
# ═══════════════════════════════════════════
coins = {
    "BTC":  "BTCUSDT",
    "ETH":  "ETHUSDT",
    "BNB":  "BNBUSDT",
    "SOL":  "SOLUSDT",
    "LTC":  "LTCUSDT",
    "TON":  "TONUSDT",
    "TRX":  "TRXUSDT",
    "DOGE": "DOGEUSDT",
}

emoji_id = {
    "BTC":  "5215277894456089919",
    "ETH":  "5215469686220688535",
    "BNB":  "5215501052366852398",
    "SOL":  "5215644439850028163",
    "LTC":  "5215397251597243962",
    "TON":  "5215541953340410399",
    "TRX":  "5215676493190960888",
    "DOGE": "5215580724010193095",
}

# ═══════════════════════════════════════════
#  FOYDALANUVCHI HOLATI
# ═══════════════════════════════════════════
users: dict[int, dict] = {}
users_lock = threading.Lock()

# ═══════════════════════════════════════════
#  BINANCE API
# ═══════════════════════════════════════════
def get_prices() -> dict:
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=5)
        data = r.json()
        result = {}
        for item in data:
            for coin, symbol in coins.items():
                if item["symbol"] == symbol:
                    result[coin] = {
                        "price":  float(item["lastPrice"]),
                        "change": float(item["priceChangePercent"]),
                        "high":   float(item["highPrice"]),
                        "low":    float(item["lowPrice"]),
                        "volume": float(item["quoteVolume"]),
                    }
        return result
    except Exception:
        return {}

# ═══════════════════════════════════════════
#  XABAR QURUVCHILAR
# ═══════════════════════════════════════════
def fmt_coin(coin: str) -> str:
    return f"<tg-emoji emoji-id='{emoji_id[coin]}'>🪙</tg-emoji> <b>{coin}</b>"

def build_prices(prices: dict, prev: dict, interval: int) -> str:
    t = datetime.now().strftime("%H:%M:%S")
    lines = ["<b>💰 Kripto Narxlar</b>\n"]
    for coin, info in prices.items():
        price  = info["price"]
        prev_p = prev.get(coin, {}).get("price", price)
        arrow  = "🟢" if price > prev_p else ("🔴" if price < prev_p else "⚪")
        change = info["change"]
        ch_str = f"{'🟢 +' if change > 0 else '🔴 '}{change:.2f}%"
        lines.append(f"{fmt_coin(coin)}  {arrow}  <code>${price:,.4f}</code>  {ch_str}")
    lines.append(f"\n🕐 {t}  |  🔄 {interval}s")
    return "\n".join(lines)

def build_stats(prices: dict) -> str:
    t = datetime.now().strftime("%H:%M:%S")
    lines = ["<b>📊 24 Soatlik Statistika</b>\n"]
    for coin, info in prices.items():
        lines.append(
            f"{fmt_coin(coin)}\n"
            f"   💵 Narx:    <code>${info['price']:,.4f}</code>\n"
            f"   📈 Max:     <code>${info['high']:,.4f}</code>\n"
            f"   📉 Min:     <code>${info['low']:,.4f}</code>\n"
            f"   🔄 O'zgarish: <b>{'+'if info['change']>0 else ''}{info['change']:.2f}%</b>\n"
            f"   💹 Volume:  <code>${info['volume']:,.0f}</code>\n"
        )
    lines.append(f"🕐 {t}")
    return "\n".join(lines)

def build_settings(user: dict) -> str:
    return (
        "<b>⚙️ Sozlamalar</b>\n\n"
        f"🔄 Yangilanish intervali: <b>{user['interval']} soniya</b>\n\n"
        "Intervalni o'zgartirish uchun quyidagi tugmani bosing:"
    )

def build_alerts(user: dict) -> str:
    lines = ["<b>🔔 Signal / Alert</b>\n"]
    alerts = user.get("alerts", {})
    has_any = any(v["above"] or v["below"] for v in alerts.values())
    if not has_any:
        lines.append("⚠️ Hozircha hech qanday signal o'rnatilmagan.\n")
    else:
        for coin, a in alerts.items():
            if a["above"] or a["below"]:
                lines.append(f"{fmt_coin(coin)}")
                if a["above"]: lines.append(f"   🔼 Yuqori: <code>${a['above']:,.4f}</code>")
                if a["below"]: lines.append(f"   🔽 Quyi:   <code>${a['below']:,.4f}</code>")
                lines.append("")
    lines.append("➕ Signal qo'shish:  /alert BTC above 70000")
    lines.append("🗑 O'chirish:        /delalert BTC")
    return "\n".join(lines)

# ═══════════════════════════════════════════
#  KLAVIATURALAR
# ═══════════════════════════════════════════
def main_reply_kb():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💰 Narxlar", "📊 Statistika")
    kb.row("🔔 Signallar", "⚙️ Sozlamalar")
    return kb

def prices_inline_kb(active: bool):
    kb = telebot.types.InlineKeyboardMarkup()
    lbl, cb = ("⏹ To'xtatish", "stop") if active else ("▶️ Boshlash", "resume")
    kb.row(
        telebot.types.InlineKeyboardButton(lbl, callback_data=cb),
        telebot.types.InlineKeyboardButton("🔃 Yangilash", callback_data="refresh"),
    )
    return kb

def stats_inline_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🔃 Yangilash", callback_data="stats_refresh"))
    return kb

def settings_inline_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    row = []
    for s in [3, 5, 10, 30, 60]:
        row.append(telebot.types.InlineKeyboardButton(f"⏱ {s}s", callback_data=f"setinterval_{s}"))
    kb.row(*row)
    return kb

def alerts_inline_kb():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🗑 Barcha signallarni o'chirish", callback_data="clear_alerts"))
    return kb

# ═══════════════════════════════════════════
#  ALERT TEKSHIRUVI
# ═══════════════════════════════════════════
def check_alerts(chat_id: int, prices: dict, user: dict):
    alerts = user.get("alerts", {})
    for coin, a in alerts.items():
        info = prices.get(coin)
        if not info:
            continue
        price = info["price"]
        if a["above"] and price >= a["above"]:
            bot.send_message(
                chat_id,
                f"🔔 <b>SIGNAL!</b>\n{fmt_coin(coin)} — <code>${price:,.4f}</code>\n"
                f"🔼 Chegara: <code>${a['above']:,.4f}</code> dan oshdi!",
                parse_mode="HTML"
            )
            with users_lock:
                users[chat_id]["alerts"][coin]["above"] = None
        if a["below"] and price <= a["below"]:
            bot.send_message(
                chat_id,
                f"🔔 <b>SIGNAL!</b>\n{fmt_coin(coin)} — <code>${price:,.4f}</code>\n"
                f"🔽 Chegara: <code>${a['below']:,.4f}</code> dan tushdi!",
                parse_mode="HTML"
            )
            with users_lock:
                users[chat_id]["alerts"][coin]["below"] = None

# ═══════════════════════════════════════════
#  AUTO-YANGILANISH THREADI
# ═══════════════════════════════════════════
def updater_thread(chat_id: int):
    while True:
        with users_lock:
            user = users.get(chat_id)
            if not user:
                return
            active   = user["active"]
            interval = user["interval"]
            msg_id   = user["message_id"]
            section  = user.get("section", "prices")
            prev     = user.get("prev_prices", {})

        if not active:
            time.sleep(1)
            continue

        prices = get_prices()
        if not prices:
            time.sleep(interval)
            continue

        with users_lock:
            u = dict(users.get(chat_id, {}))
        check_alerts(chat_id, prices, u)

        if section == "prices":
            text = build_prices(prices, prev, interval)
            try:
                bot.edit_message_text(
                    text, chat_id, msg_id,
                    parse_mode="HTML",
                    reply_markup=prices_inline_kb(active=True)
                )
            except Exception:
                pass

        with users_lock:
            if chat_id in users:
                users[chat_id]["prev_prices"] = prices

        time.sleep(interval)

# ═══════════════════════════════════════════
#  YORDAMCHI
# ═══════════════════════════════════════════
def ensure_user(chat_id: int, message_id: int = 0):
    with users_lock:
        if chat_id not in users:
            users[chat_id] = {
                "message_id":  message_id,
                "active":      True,
                "interval":    DEFAULT_INTERVAL,
                "prev_prices": {},
                "section":     "prices",
                "alerts":      {c: {"above": None, "below": None} for c in coins},
            }
            t = threading.Thread(target=updater_thread, args=(chat_id,), daemon=True)
            t.start()

# ═══════════════════════════════════════════
#  BUYRUQLAR
# ═══════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(message):
    chat_id = message.chat.id
    bot.send_message(
        chat_id,
        "👋 <b>AlphaCryptoBot</b> ga xush kelibsiz!\n\nQuyidagi menyudan bo'lim tanlang 👇",
        parse_mode="HTML",
        reply_markup=main_reply_kb()
    )
    prices = get_prices()
    text = build_prices(prices, {}, DEFAULT_INTERVAL)
    sent = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=prices_inline_kb(active=True))
    ensure_user(chat_id, sent.message_id)
    with users_lock:
        users[chat_id].update({
            "message_id":  sent.message_id,
            "prev_prices": prices,
            "section":     "prices",
            "active":      True,
        })

@bot.message_handler(commands=["alert"])
def cmd_alert(message):
    chat_id = message.chat.id
    parts = message.text.split()
    if len(parts) != 4:
        bot.reply_to(message, "⚠️ Format: /alert BTC above 70000\nYoki:    /alert ETH below 3000")
        return
    _, coin, direction, value = parts
    coin = coin.upper()
    if coin not in coins:
        bot.reply_to(message, f"❌ Noma'lum token: {coin}\nMavjud: {', '.join(coins)}")
        return
    if direction not in ("above", "below"):
        bot.reply_to(message, "❌ Yo'nalish: above yoki below")
        return
    try:
        val = float(value)
    except ValueError:
        bot.reply_to(message, "❌ Narx son bo'lishi kerak.")
        return
    ensure_user(chat_id)
    with users_lock:
        users[chat_id]["alerts"][coin][direction] = val
    d = "yuqoriga" if direction == "above" else "pastga"
    bot.reply_to(message, f"✅ {coin} narxi ${val:,.4f} dan {d} o'tganda signal keladi.")

@bot.message_handler(commands=["delalert"])
def cmd_delalert(message):
    chat_id = message.chat.id
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Format: /delalert BTC")
        return
    coin = parts[1].upper()
    ensure_user(chat_id)
    with users_lock:
        if coin in users[chat_id]["alerts"]:
            users[chat_id]["alerts"][coin] = {"above": None, "below": None}
    bot.reply_to(message, f"🗑 {coin} signallari o'chirildi.")

# ═══════════════════════════════════════════
#  REPLY KEYBOARD
# ═══════════════════════════════════════════
@bot.message_handler(func=lambda m: m.text == "💰 Narxlar")
def section_prices(message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    prices = get_prices()
    with users_lock:
        prev = users[chat_id].get("prev_prices", {})
        iv   = users[chat_id]["interval"]
        users[chat_id].update({"prev_prices": prices, "section": "prices", "active": True})
    text = build_prices(prices, prev, iv)
    sent = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=prices_inline_kb(active=True))
    with users_lock:
        users[chat_id]["message_id"] = sent.message_id

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def section_stats(message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    with users_lock:
        users[chat_id]["section"] = "stats"
    prices = get_prices()
    bot.send_message(chat_id, build_stats(prices), parse_mode="HTML", reply_markup=stats_inline_kb())

@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar")
def section_settings(message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    with users_lock:
        users[chat_id]["section"] = "settings"
        user = dict(users[chat_id])
    bot.send_message(chat_id, build_settings(user), parse_mode="HTML", reply_markup=settings_inline_kb())

@bot.message_handler(func=lambda m: m.text == "🔔 Signallar")
def section_alerts(message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    with users_lock:
        users[chat_id]["section"] = "alerts"
        user = dict(users[chat_id])
    bot.send_message(chat_id, build_alerts(user), parse_mode="HTML", reply_markup=alerts_inline_kb())

# ═══════════════════════════════════════════
#  INLINE CALLBACK
# ═══════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    ensure_user(chat_id)
    data = call.data

    if data == "stop":
        with users_lock:
            users[chat_id]["active"] = False
        try:
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=prices_inline_kb(active=False))
        except Exception: pass
        bot.answer_callback_query(call.id, "⏹ To'xtatildi.")

    elif data == "resume":
        with users_lock:
            users[chat_id].update({"active": True, "message_id": call.message.message_id, "section": "prices"})
        try:
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=prices_inline_kb(active=True))
        except Exception: pass
        bot.answer_callback_query(call.id, "▶️ Boshlandi.")

    elif data == "refresh":
        prices = get_prices()
        with users_lock:
            prev   = users[chat_id].get("prev_prices", {})
            iv     = users[chat_id]["interval"]
            active = users[chat_id]["active"]
            users[chat_id]["prev_prices"] = prices
        try:
            bot.edit_message_text(build_prices(prices, prev, iv), chat_id, call.message.message_id,
                                  parse_mode="HTML", reply_markup=prices_inline_kb(active=active))
        except Exception: pass
        bot.answer_callback_query(call.id, "✅ Yangilandi!")

    elif data == "stats_refresh":
        prices = get_prices()
        try:
            bot.edit_message_text(build_stats(prices), chat_id, call.message.message_id,
                                  parse_mode="HTML", reply_markup=stats_inline_kb())
        except Exception: pass
        bot.answer_callback_query(call.id, "✅ Yangilandi!")

    elif data.startswith("setinterval_"):
        iv = int(data.split("_")[1])
        with users_lock:
            users[chat_id]["interval"] = iv
            user = dict(users[chat_id])
        try:
            bot.edit_message_text(build_settings(user), chat_id, call.message.message_id,
                                  parse_mode="HTML", reply_markup=settings_inline_kb())
        except Exception: pass
        bot.answer_callback_query(call.id, f"✅ Interval {iv} soniya!")

    elif data == "clear_alerts":
        with users_lock:
            users[chat_id]["alerts"] = {c: {"above": None, "below": None} for c in coins}
            user = dict(users[chat_id])
        try:
            bot.edit_message_text(build_alerts(user), chat_id, call.message.message_id,
                                  parse_mode="HTML", reply_markup=alerts_inline_kb())
        except Exception: pass
        bot.answer_callback_query(call.id, "🗑 Barcha signallar o'chirildi.")

# ═══════════════════════════════════════════
#  ISHGA TUSHIRISH
# ═══════════════════════════════════════════
if __name__ == "__main__":
    print("✅ AlphaCryptoBot ishga tushdi...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
