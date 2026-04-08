import asyncio
import logging
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ========== SOZLAMALAR ==========
BOT_TOKEN = "8627453491:AAFEpPXTg-uT_wLCQ--8--7XkQPYoj_ZXuE"
ADMIN_ID = 7399101034
CHANNEL_ID = "@AlphaHookahOrders"
DB_PATH = "hookah_bot.db"

# ========== BAZA ==========
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT UNIQUE NOT NULL,
                price    INTEGER NOT NULL,
                category TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cart (
                user_id    INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity   INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, product_id)
            );
            CREATE TABLE IF NOT EXISTS orders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                products     TEXT NOT NULL,
                total        INTEGER NOT NULL,
                status       TEXT NOT NULL DEFAULT 'tolov_kutilmoqda',
                table_number TEXT NOT NULL,
                date         TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                first_name TEXT
            );
        """)
        await db.commit()
    logger.info("Ma'lumotlar bazasi tayyor.")

# ========== BOT & DISPATCHER ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== FSM ==========
class AddProduct(StatesGroup):
    name     = State()
    price    = State()
    category = State()

class DeleteProduct(StatesGroup):
    pid = State()

class OrderTable(StatesGroup):
    table_number = State()

# ========== STATUS MATNLARI ==========
STATUS_LABELS = {
    "tolov_kutilmoqda": "⏳ To'lov kutilmoqda",
    "qabul_qilingan":   "✅ Qabul qilingan",
    "yetkazilgan":      "🚚 Yetkazildi",
    "bekor_qilingan":   "❌ Bekor qilingan",
}

# ========== TUGMALAR ==========
user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍽 Menyu"),          KeyboardButton(text="🛒 Savatcha")],
        [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="📜 Buyurtmalarim")],
    ],
    resize_keyboard=True,
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Qo'shish"),    KeyboardButton(text="➖ O'chirish")],
        [KeyboardButton(text="📋 Buyurtmalar"), KeyboardButton(text="📊 Statistika")],
    ],
    resize_keyboard=True,
)

# ========== YORDAMCHI: INLINE KB ==========
def make_inline(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """rows = [ [(text, callback_data), ...], ... ]"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows]
    )

# ========== KANALGA XABAR ==========
async def send_to_channel(order_id: int, event_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT o.user_id, o.products, o.total, o.table_number, o.date, u.first_name "
            "FROM orders o LEFT JOIN users u ON o.user_id = u.user_id WHERE o.id=?",
            (order_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return

    user_id, products, total, table, date, first_name = row
    user_name = first_name or str(user_id)

    try:
        date_f = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
    except ValueError:
        date_f = date

    titles = {
        "new":       ("🍃 Yangi buyurtma",      STATUS_LABELS["tolov_kutilmoqda"]),
        "paid":      ("💳 To'lov tasdiqlandi",   STATUS_LABELS["qabul_qilingan"]),
        "delivered": ("🚀 Buyurtma yetkazildi",  STATUS_LABELS["yetkazilgan"]),
    }
    if event_type not in titles:
        return
    title, status_label = titles[event_type]

    text = (
        f"<b>{title}</b>\n"
        f"🆔 Buyurtma: <b>#{order_id}</b>\n"
        f"👤 Mijoz: {user_name}\n"
        f"📦 Mahsulotlar: {products}\n"
        f"💰 Jami: <b>{total:,} so'm</b>\n"
        f"🪑 Stol: {table}\n"
        f"🔎 Holat: {status_label}\n"
        f"🕐 Vaqt: {date_f}"
    )
    try:
        await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Kanalga xabar yuborib bo'lmadi: {e}")

# ========== /start ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid  = message.from_user.id
    name = message.from_user.first_name or ""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", (uid, name)
        )
        await db.commit()

    if uid == ADMIN_ID:
        await message.answer("👑 Xush kelibsiz, Admin!", reply_markup=admin_menu)
    else:
        await message.answer(
            f"🍃 <b>AlphaHookah</b> botiga xush kelibsiz, {name}!\n"
            "Quyidagi menyu orqali buyurtma bering.",
            parse_mode="HTML",
            reply_markup=user_menu,
        )

# ========== MENYU ==========
@dp.message(lambda m: m.text == "🍽 Menyu")
async def show_menu(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT category FROM products ORDER BY category") as cur:
            cats = await cur.fetchall()
    if not cats:
        await message.answer("❌ Hozircha mahsulotlar yo'q.")
        return
    kb = make_inline([[(f"📂 {c[0].capitalize()}", f"cat_{c[0]}")] for c in cats])
    await message.answer("📋 <b>Kategoriya tanlang:</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat = callback.data[4:]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, name, price FROM products WHERE category=? ORDER BY name", (cat,)
        ) as cur:
            prods = await cur.fetchall()
    if not prods:
        await callback.answer("Bu kategoriyada mahsulot yo'q.", show_alert=True)
        return

    lines = "\n".join(f"  • {name} — <b>{price:,} so'm</b>" for _, name, price in prods)
    text  = f"📂 <b>{cat.upper()}</b>\n\n{lines}"
    rows  = [[( f"➕ {name}", f"add_{pid}")] for pid, name, _ in prods]
    rows += [[("🔙 Kategoriyalar", "back_cat")]]
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=make_inline(rows))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_cat")
async def back_to_categories(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT category FROM products ORDER BY category") as cur:
            cats = await cur.fetchall()
    if not cats:
        await callback.answer("Mahsulot yo'q.", show_alert=True)
        return
    kb = make_inline([[(f"📂 {c[0].capitalize()}", f"cat_{c[0]}")] for c in cats])
    await callback.message.edit_text("📋 <b>Kategoriya tanlang:</b>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    pid     = int(callback.data[4:])
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        # cart jadvalida PRIMARY KEY (user_id, product_id) bor — conflict bo'lsa qty oshiramiz
        await db.execute(
            "INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + 1",
            (user_id, pid),
        )
        await db.commit()
    await callback.answer("✅ Savatchaga qo'shildi!", show_alert=False)

# ========== SAVATCHA ==========
async def _get_cart(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT p.id, p.name, p.price, c.quantity "
            "FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?",
            (user_id,),
        ) as cur:
            return await cur.fetchall()

@dp.message(lambda m: m.text in ("🛒 Savatcha", "📦 Buyurtma berish"))
async def show_cart(message: types.Message):
    items = await _get_cart(message.from_user.id)
    if not items:
        await message.answer("🛒 Savatchangiz bo'sh.\n«🍽 Menyu» orqali mahsulot qo'shing.")
        return

    lines = "\n".join(f"  {name} × {qty} = <b>{price*qty:,} so'm</b>" for _, name, price, qty in items)
    total = sum(p * q for _, _, p, q in items)
    text  = f"🛍 <b>Savatcha</b>\n\n{lines}\n\n💰 Jami: <b>{total:,} so'm</b>"
    kb    = make_inline([
        [("🚀 Buyurtma berish", "order_now")],
        [("🗑 Savatchani tozalash", "clear_cart")],
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id=?", (callback.from_user.id,))
        await db.commit()
    await callback.answer("🗑 Savatcha tozalandi!", show_alert=True)
    await callback.message.delete()

# ========== BUYURTMA ==========
@dp.callback_query(lambda c: c.data == "order_now")
async def order_start(callback: types.CallbackQuery, state: FSMContext):
    items = await _get_cart(callback.from_user.id)
    if not items:
        await callback.answer("Savatcha bo'sh!", show_alert=True)
        return
    await callback.message.answer("🪑 Stol raqamingizni yozing (masalan: <b>15</b>):", parse_mode="HTML")
    await state.set_state(OrderTable.table_number)
    await callback.answer()

@dp.message(OrderTable.table_number)
async def get_table_number(message: types.Message, state: FSMContext):
    table = message.text.strip()
    if not table:
        await message.answer("Stol raqamini kiriting!")
        return

    uid   = message.from_user.id
    items = await _get_cart(uid)
    if not items:
        await message.answer("Savatcha bo'sh. Buyurtma bekor qilindi.")
        await state.clear()
        return

    total    = sum(p * q for _, _, p, q in items)
    prod_txt = ", ".join(f"{n} ×{q}" for _, n, _, q in items)
    now      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders (user_id, products, total, status, table_number, date) "
            "VALUES (?, ?, ?, 'tolov_kutilmoqda', ?, ?)",
            (uid, prod_txt, total, table, now),
        )
        order_id = cur.lastrowid
        await db.execute("DELETE FROM cart WHERE user_id=?", (uid,))
        await db.commit()

    await message.answer(
        f"📦 <b>Buyurtma #{order_id}</b> qabul qilindi!\n\n"
        f"🪑 Stol: <b>{table}</b>\n"
        f"📋 {prod_txt}\n"
        f"💰 Jami: <b>{total:,} so'm</b>\n\n"
        f"💳 To'lov uchun karta: <code>8600 1234 5678 9012</code>\n"
        "To'lov qilgach quyidagi tugmani bosing 👇",
        parse_mode="HTML",
        reply_markup=make_inline([[("✅ To'lov qildim", f"paid_{order_id}")]]),
    )

    await send_to_channel(order_id, "new")
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
            f"👤 User ID: {uid}\n"
            f"🪑 Stol: {table}\n"
            f"📦 {prod_txt}\n"
            f"💰 {total:,} so'm",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Adminga xabar yuborib bo'lmadi: {e}")

    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def user_paid(callback: types.CallbackQuery):
    order_id = int(callback.data[5:])
    uid      = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT products, total FROM orders WHERE id=? AND user_id=? AND status='tolov_kutilmoqda'",
            (order_id, uid),
        ) as cur:
            row = await cur.fetchone()

    if not row:
        await callback.answer("❌ Buyurtma topilmadi yoki allaqachon qayta ishlangan!", show_alert=True)
        return

    prods, total = row
    try:
        await bot.send_message(
            ADMIN_ID,
            f"💳 <b>To'lov bildirildi — #{order_id}</b>\n"
            f"📦 {prods}\n"
            f"💰 {total:,} so'm",
            parse_mode="HTML",
            reply_markup=make_inline([[
                ("✅ Tasdiqlash", f"confirm_{order_id}"),
                ("❌ Rad etish",  f"reject_{order_id}"),
            ]]),
        )
    except Exception as e:
        logger.warning(f"Adminga to'lov xabari yuborib bo'lmadi: {e}")

    await callback.message.answer("✅ To'lov ma'lumotingiz adminga yuborildi. Tasdiq kutilmoqda.")
    await callback.answer()

# ========== ADMIN AMALLAR ==========
def _admin_only(func):
    """Admin emasni bloklash uchun dekorator."""
    async def wrapper(callback: types.CallbackQuery, *args, **kwargs):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("⛔ Faqat admin!", show_alert=True)
            return
        return await func(callback, *args, **kwargs)
    return wrapper

@dp.callback_query(lambda c: c.data.startswith("confirm_"))
@_admin_only
async def confirm_payment(callback: types.CallbackQuery):
    order_id = int(callback.data[8:])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM orders WHERE id=? AND status='tolov_kutilmoqda'", (order_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            await callback.answer("Buyurtma topilmadi yoki holati o'zgargan!", show_alert=True)
            return
        await db.execute("UPDATE orders SET status='qabul_qilingan' WHERE id=?", (order_id,))
        await db.commit()

    try:
        await bot.send_message(row[0], f"✅ <b>#{order_id}</b> buyurtmangiz to'lovi tasdiqlandi! Tayyorlanmoqda 🍃", parse_mode="HTML")
    except Exception as e:
        logger.warning(e)

    await send_to_channel(order_id, "paid")
    await callback.message.edit_text(
        f"✅ Buyurtma <b>#{order_id}</b> tasdiqlandi.",
        parse_mode="HTML",
        reply_markup=make_inline([[("🚚 Yetkazildi", f"deliver_{order_id}")]]),
    )
    await callback.answer("Tasdiqlandi!")

@dp.callback_query(lambda c: c.data.startswith("deliver_"))
@_admin_only
async def deliver_order(callback: types.CallbackQuery):
    order_id = int(callback.data[8:])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM orders WHERE id=? AND status='qabul_qilingan'", (order_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            await callback.answer("Buyurtma topilmadi yoki holati noto'g'ri!", show_alert=True)
            return
        await db.execute("UPDATE orders SET status='yetkazilgan' WHERE id=?", (order_id,))
        await db.commit()

    try:
        await bot.send_message(row[0], f"🚀 <b>#{order_id}</b> buyurtmangiz yetkazildi. Rahmat! 🙏", parse_mode="HTML")
    except Exception as e:
        logger.warning(e)

    await send_to_channel(order_id, "delivered")
    await callback.message.edit_text(f"🚚 Buyurtma <b>#{order_id}</b> yetkazildi.", parse_mode="HTML")
    await callback.answer("Yetkazildi!")

@dp.callback_query(lambda c: c.data.startswith("reject_"))
@_admin_only
async def reject_payment(callback: types.CallbackQuery):
    order_id = int(callback.data[7:])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM orders WHERE id=?", (order_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            await callback.answer("Buyurtma topilmadi!", show_alert=True)
            return
        await db.execute("UPDATE orders SET status='bekor_qilingan' WHERE id=?", (order_id,))
        await db.commit()

    try:
        await bot.send_message(row[0], f"❌ <b>#{order_id}</b> buyurtmangiz to'lovi rad etildi.", parse_mode="HTML")
    except Exception as e:
        logger.warning(e)

    await callback.message.edit_text(f"❌ Buyurtma <b>#{order_id}</b> rad etildi.", parse_mode="HTML")
    await callback.answer("Rad etildi.")

# ========== BUYURTMA TARIXI ==========
@dp.message(lambda m: m.text == "📜 Buyurtmalarim")
async def my_orders(message: types.Message):
    uid = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, products, total, status, table_number, date "
            "FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (uid,),
        ) as cur:
            orders = await cur.fetchall()
    if not orders:
        await message.answer("Siz hali buyurtma bermagansiz.")
        return
    lines = []
    for oid, prods, total, status, table, date in orders:
        label = STATUS_LABELS.get(status, status)
        lines.append(
            f"🔹 <b>#{oid}</b> | {label}\n"
            f"   🪑 Stol: {table} | 💰 {total:,} so'm\n"
            f"   📦 {prods}\n"
            f"   🕐 {date}"
        )
    await message.answer("📜 <b>So'nggi buyurtmalaringiz:</b>\n\n" + "\n\n".join(lines), parse_mode="HTML")

# ========== ADMIN — MAHSULOT QO'SHISH ==========
@dp.message(lambda m: m.text == "➕ Qo'shish" and m.from_user.id == ADMIN_ID)
async def add_start(message: types.Message, state: FSMContext):
    await message.answer("📝 Mahsulot nomini yuboring:")
    await state.set_state(AddProduct.name)

@dp.message(AddProduct.name)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("💰 Narxini raqamda yuboring (masalan: <code>100000</code>):", parse_mode="HTML")
    await state.set_state(AddProduct.price)

@dp.message(AddProduct.price)
async def add_price(message: types.Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam kiriting! Masalan: <code>100000</code>", parse_mode="HTML")
        return
    await state.update_data(price=int(message.text.strip()))
    await message.answer("📂 Kategoriyasini yuboring (masalan: <code>nargile</code>, <code>aroma</code>, <code>ichimlik</code>):", parse_mode="HTML")
    await state.set_state(AddProduct.category)

@dp.message(AddProduct.category)
async def add_category(message: types.Message, state: FSMContext):
    cat  = message.text.strip().lower()
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO products (name, price, category) VALUES (?, ?, ?)",
                (data["name"], data["price"], cat),
            )
            await db.commit()
            await message.answer(f"✅ <b>{data['name']}</b> muvaffaqiyatli qo'shildi!", parse_mode="HTML")
        except aiosqlite.IntegrityError:
            await message.answer("❌ Bu nomli mahsulot allaqachon mavjud.")
    await state.clear()

# ========== ADMIN — MAHSULOT O'CHIRISH ==========
@dp.message(lambda m: m.text == "➖ O'chirish" and m.from_user.id == ADMIN_ID)
async def delete_start(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, price FROM products ORDER BY category, name") as cur:
            prods = await cur.fetchall()
    if not prods:
        await message.answer("❌ Mahsulot yo'q.")
        return
    lines = "\n".join(f"  <code>{pid}</code> — {name} ({price:,} so'm)" for pid, name, price in prods)
    await message.answer(f"🗑 O'chirish uchun <b>ID</b> raqamini yuboring:\n\n{lines}", parse_mode="HTML")
    await state.set_state(DeleteProduct.pid)

@dp.message(DeleteProduct.pid)
async def delete_pid(message: types.Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ ID raqam bo'lishi kerak!")
        return
    pid = int(message.text.strip())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM products WHERE id=?", (pid,)) as cur:
            row = await cur.fetchone()
        if not row:
            await message.answer("❌ Bunday ID topilmadi.")
        else:
            await db.execute("DELETE FROM products WHERE id=?", (pid,))
            await db.commit()
            await message.answer(f"✅ <b>{row[0]}</b> o'chirildi.", parse_mode="HTML")
    await state.clear()

# ========== ADMIN — BUYURTMALAR ==========
@dp.message(lambda m: m.text == "📋 Buyurtmalar" and m.from_user.id == ADMIN_ID)
async def list_orders(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, user_id, products, total, status, table_number, date "
            "FROM orders ORDER BY id DESC LIMIT 20"
        ) as cur:
            orders = await cur.fetchall()
    if not orders:
        await message.answer("Buyurtmalar yo'q.")
        return
    lines = []
    for oid, uid, prods, total, status, table, date in orders:
        label = STATUS_LABELS.get(status, status)
        lines.append(
            f"🔹 <b>#{oid}</b> | {label}\n"
            f"   👤 {uid} | 🪑 {table} | 💰 {total:,} so'm\n"
            f"   📦 {prods}\n"
            f"   🕐 {date}"
        )
    await message.answer("📋 <b>Oxirgi 20 buyurtma:</b>\n\n" + "\n\n".join(lines), parse_mode="HTML")

# ========== ADMIN — STATISTIKA ==========
@dp.message(lambda m: m.text == "📊 Statistika" and m.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            total_orders = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(total) FROM orders WHERE status='yetkazilgan'") as cur:
            revenue = (await cur.fetchone())[0] or 0
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='tolov_kutilmoqda'") as cur:
            pending = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM products") as cur:
            total_products = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]

    await message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"📦 Jami buyurtmalar: <b>{total_orders}</b>\n"
        f"⏳ To'lov kutilyapti: <b>{pending}</b>\n"
        f"💰 Umumiy daromad: <b>{revenue:,} so'm</b>\n"
        f"🍃 Mahsulotlar: <b>{total_products}</b>\n"
        f"👥 Foydalanuvchilar: <b>{total_users}</b>",
        parse_mode="HTML",
    )

# ========== ISHGA TUSHIRISH ==========
async def main():
    await init_db()
    logger.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
