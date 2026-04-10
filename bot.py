import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== SOZLAMALAR ==========
BOT_TOKEN = "8627453491:AAFEpPXTg-uT_wLCQ--8--7XkQPYoj_ZXuE"
ADMIN_ID = 7399101034 
CHANNEL_ID = "@AlphaHookahOrders"  # Kanal username yoki ID

# ========== BAZA ==========
DB_PATH = "hookah_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                price INTEGER,
                category TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                products TEXT,
                total INTEGER,
                status TEXT,
                table_number TEXT,
                date TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channel_messages (
                order_id INTEGER PRIMARY KEY,
                message_id INTEGER
            )
        """)
        await db.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== FSM ==========
class AddProduct(StatesGroup):
    name = State()
    price = State()
    category = State()

class DeleteProduct(StatesGroup):
    pid = State()

class OrderTable(StatesGroup):
    table_number = State()

class ConfirmTable(StatesGroup):
    waiting_confirmation = State()

# ========== TUGMALAR ==========
user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍽 Menyu"), KeyboardButton(text="🛒 Savatcha")],
        [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="📜 Mening buyurtmalarim")]
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Mahsulot qo'shish"), KeyboardButton(text="❌ Mahsulot o'chirish")],
        [KeyboardButton(text="📋 Buyurtmalar"), KeyboardButton(text="📊 Statistika")]
    ],
    resize_keyboard=True
)

# ========== KANAL XABARINI YUBORISH VA YANGILASH ==========
async def send_or_update_channel_message(order_id, event_type):
    """Kanalga xabar yuboradi yoki mavjud xabarni yangilaydi"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT o.user_id, o.products, o.total, o.table_number, o.date, o.status, u.first_name 
            FROM orders o LEFT JOIN users u ON o.user_id = u.user_id 
            WHERE o.id = ?
        """, (order_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return
        user_id, products, total, table, date, status, first_name = row
        user_name = first_name or str(user_id)
        date_f = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
        
        # Holatga qarab emoji va matn
        if status == "toʻlov_kutilmoqda":
            status_emoji = "⏳"
            status_text = "Toʻlov kutilmoqda"
            title = "🆕 YANGI BUYURTMA"
        elif status == "qabul_qilingan":
            status_emoji = "✅"
            status_text = "Toʻlov tasdiqlandi"
            title = "💰 TOʻLOV TASDIQLANDI"
        elif status == "yetkazilgan":
            status_emoji = "🚚"
            status_text = "Yetkazib berildi"
            title = "✅ BUYURTMA YETKAZILDI"
        elif status == "bekor_qilingan":
            status_emoji = "❌"
            status_text = "Bekor qilindi"
            title = "❌ BUYURTMA BEKOR QILINDI"
        else:
            status_emoji = "❓"
            status_text = status
            title = "📦 BUYURTMA"
        
        # Chiroyli xabar formati
        text = f"""
<b>{title}</b>
━━━━━━━━━━━━━━━━━━━━
🆔 <b>#{order_id}</b>
👤 <b>{user_name}</b>
🪑 <b>{table}</b>-stol
📦 <b>{products}</b>
💰 <b>{total:,}</b> so'm
━━━━━━━━━━━━━━━━━━━━
{status_emoji} Holat: <b>{status_text}</b>
📝 {date_f}
"""
        # Kanalga xabar yuborish yoki yangilash
        async with db.execute("SELECT message_id FROM channel_messages WHERE order_id=?", (order_id,)) as cur:
            msg_row = await cur.fetchone()
        
        try:
            if msg_row:
                # Xabar bor – yangilaymiz
                await bot.edit_message_text(
                    chat_id=CHANNEL_ID,
                    message_id=msg_row[0],
                    text=text,
                    parse_mode="HTML"
                )
            else:
                # Xabar yo'q – yangi yuboramiz
                sent = await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
                await db.execute("INSERT INTO channel_messages (order_id, message_id) VALUES (?, ?)", (order_id, sent.message_id))
                await db.commit()
        except Exception as e:
            print(f"Kanal xabari xatosi: {e}")

# ========== START ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or ""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", (user_id, first_name))
        await db.commit()
    if user_id == ADMIN_ID:
        await message.answer("👑 Admin panelga xush kelibsiz!", reply_markup=admin_menu)
    else:
        await message.answer("🍃 AlphaHookah bar botiga xush kelibsiz!", reply_markup=user_menu)

# ========== MENYU ==========
@dp.message(lambda msg: msg.text == "🍽 Menyu")
async def show_menu(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT category FROM products") as cur:
            cats = await cur.fetchall()
    if not cats:
        await message.answer("❌ Hozircha mahsulot yo‘q. Admin tomonidan qo‘shiladi.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for (cat,) in cats:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"📁 {cat.upper()}", callback_data=f"cat_{cat}")])
    await message.answer("📋 Kategoriyani tanlang:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat = callback.data.split("_")[1]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, price FROM products WHERE category=?", (cat,)) as cur:
            prods = await cur.fetchall()
    
    if not prods:
        await callback.answer("Bu kategoriyada mahsulot yo'q", show_alert=True)
        return
    
    text = f"📋 <b>{cat.upper()}</b>:\n\n" + "\n".join([f"🍃 {name} — {price:,} so'm" for _, name, price in prods])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"➕ {name}", callback_data=f"add_{pid}")] for pid, name, _ in prods
    ] + [[InlineKeyboardButton(text="◀️ Ortga", callback_data="back_cat")]])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_cat")
async def back_cat(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT category FROM products") as cur:
            cats = await cur.fetchall()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📁 {cat[0].upper()}", callback_data=f"cat_{cat[0]}")] for cat in cats])
    await callback.message.edit_text("📋 Kategoriyani tanlang:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM products WHERE id=?", (pid,)) as cur:
            if not await cur.fetchone():
                await callback.answer("Mahsulot topilmadi!", show_alert=True)
                return
        await db.execute("""
            INSERT INTO cart (user_id, product_id, quantity) 
            VALUES (?, ?, 1) 
            ON CONFLICT DO UPDATE SET quantity = quantity + 1
        """, (user_id, pid))
        await db.commit()
    
    await callback.answer("✅ Savatchaga qo'shildi!", show_alert=True)

# ========== SAVATCHA ==========
@dp.message(lambda msg: msg.text == "🛒 Savatcha")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.id, p.name, p.price, c.quantity 
            FROM cart c JOIN products p ON c.product_id = p.id 
            WHERE c.user_id = ?
        """, (user_id,)) as cur:
            items = await cur.fetchall()
    
    if not items:
        await message.answer("🛒 Savatcha bo'sh.")
        return
    
    total = 0
    text = "🛍 <b>Savatchangiz</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    for pid, name, price, qty in items:
        subtotal = price * qty
        total += subtotal
        text += f"• {name} x{qty} = {subtotal:,} so'm\n"
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="➖", callback_data=f"dec_{pid}"),
            InlineKeyboardButton(text=f"{qty}", callback_data="ignore"),
            InlineKeyboardButton(text="➕", callback_data=f"inc_{pid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"rem_{pid}")
        ])
    
    text += f"━━━━━━━━━━━━━━━━━━━━\n💰 <b>Jami: {total:,} so'm</b>"
    kb.inline_keyboard.append([InlineKeyboardButton(text="🚀 Buyurtma berish", callback_data="order_now")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart")])
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("inc_"))
async def inc_qty(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE cart SET quantity = quantity + 1 WHERE user_id=? AND product_id=?", (callback.from_user.id, pid))
        await db.commit()
    await show_cart(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("dec_"))
async def dec_qty(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT quantity FROM cart WHERE user_id=? AND product_id=?", (user_id, pid)) as cur:
            row = await cur.fetchone()
        if row and row[0] > 1:
            await db.execute("UPDATE cart SET quantity = quantity - 1 WHERE user_id=? AND product_id=?", (user_id, pid))
        else:
            await db.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (user_id, pid))
        await db.commit()
    await show_cart(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("rem_"))
async def rem_item(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (callback.from_user.id, pid))
        await db.commit()
    await show_cart(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id=?", (callback.from_user.id,))
        await db.commit()
    await callback.answer("Savatcha tozalandi!", show_alert=True)
    await callback.message.delete()

# ========== BUYURTMA ==========
@dp.callback_query(lambda c: c.data == "order_now")
async def order_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM cart WHERE user_id=?", (user_id,)) as cur:
            count = (await cur.fetchone())[0]
    
    if count == 0:
        await callback.answer("Savatcha bo'sh!", show_alert=True)
        return
    
    await callback.message.answer("🪑 Stol raqamingizni yozing (masalan: 15):")
    await state.set_state(OrderTable.table_number)
    await callback.answer()

@dp.message(OrderTable.table_number)
async def get_table_number(message: types.Message, state: FSMContext):
    table_number = message.text.strip()
    await state.update_data(table_number=table_number)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, to'g'ri", callback_data="confirm_table"),
         InlineKeyboardButton(text="❌ Yo'q, qayta", callback_data="retry_table")]
    ])
    await message.answer(f"🪑 Stol raqami: <b>{table_number}</b>\n\nTo'g'rimi?", parse_mode="HTML", reply_markup=kb)
    await state.set_state(ConfirmTable.waiting_confirmation)

@dp.callback_query(lambda c: c.data == "confirm_table")
async def confirm_table(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    table_number = data.get('table_number')
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT p.name, p.price, c.quantity 
            FROM cart c JOIN products p ON c.product_id = p.id 
            WHERE c.user_id = ?
        """, (user_id,)) as cur:
            items = await cur.fetchall()
    
    if not items:
        await callback.message.answer("Savatcha bo'sh. Buyurtma bekor qilindi.")
        await state.clear()
        return
    
    total = sum(price * qty for _, price, qty in items)
    products_text = ", ".join([f"{name} x{qty}" for name, _, qty in items])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO orders (user_id, products, total, status, table_number, date) 
            VALUES (?, ?, ?, 'toʻlov_kutilmoqda', ?, ?)
        """, (user_id, products_text, total, table_number, now))
        await db.commit()
        order_id = cur.lastrowid
        await db.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
        await db.commit()
    
    # Kanalga xabar yuborish
    await send_or_update_channel_message(order_id, "new")
    
    # Admin xabar
    await bot.send_message(ADMIN_ID, 
        f"🆕 Yangi buyurtma #{order_id}\n"
        f"👤 ID: {user_id}\n"
        f"🪑 Stol: {table_number}\n"
        f"📦: {products_text}\n"
        f"💰: {total:,} so'm"
    )
    
    # Foydalanuvchiga xabar
    await callback.message.edit_text(
        f"✅ <b>Buyurtma #{order_id} qabul qilindi!</b>\n\n"
        f"🪑 Stol: {table_number}\n"
        f"💰 Jami: {total:,} so'm\n\n"
        f"💳 <b>To‘lov uchun:</b>\n"
        f"🏦 8600 1234 5678 9012 (Humo/MyUzcard)\n\n"
        f"To‘lov qilgach <b>✅ To‘lov qildim</b> tugmasini bosing.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ To‘lov qildim", callback_data=f"paid_{order_id}")]
        ])
    )
    await state.clear()

@dp.callback_query(lambda c: c.data == "retry_table")
async def retry_table(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🪑 Stol raqamingizni qayta yozing:")
    await state.set_state(OrderTable.table_number)
    await callback.answer()

# ========== TO'LOV BILDIRISH ==========
@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def user_paid(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT products, total, status FROM orders WHERE id=? AND user_id=?", (order_id, user_id)) as cur:
            row = await cur.fetchone()
        if not row:
            await callback.answer("Buyurtma topilmadi!", show_alert=True)
            return
        if row[2] != "toʻlov_kutilmoqda":
            await callback.answer(f"Buyurtma allaqachon {row[2]}!", show_alert=True)
            return
        prods, total = row[0], row[1]
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ To'lovni tasdiqlash", callback_data=f"admin_confirm_{order_id}"),
         InlineKeyboardButton(text="❌ To'lovni rad etish", callback_data=f"admin_reject_{order_id}")]
    ])
    
    await bot.send_message(ADMIN_ID, 
        f"💳 <b>To‘lov bildirildi #{order_id}</b>\n"
        f"👤 Foydalanuvchi: {user_id}\n"
        f"📦: {prods}\n"
        f"💰: {total:,} so'm",
        parse_mode="HTML",
        reply_markup=admin_kb
    )
    await callback.message.answer("✅ To‘lov ma'lumotingiz adminga yuborildi. Tez orada tasdiqlanadi.")
    await callback.answer()

# ========== ADMIN TASDIQLASH ==========
@dp.callback_query(lambda c: c.data.startswith("admin_confirm_"))
async def admin_confirm(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, status FROM orders WHERE id=?", (order_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            await callback.answer("Buyurtma topilmadi!")
            return
        if row[1] != "toʻlov_kutilmoqda":
            await callback.answer(f"Buyurtma allaqachon {row[1]}!")
            return
        user_id = row[0]
        await db.execute("UPDATE orders SET status='qabul_qilingan' WHERE id=?", (order_id,))
        await db.commit()
    
    # Kanal xabarini yangilash
    await send_or_update_channel_message(order_id, "paid")
    
    # Foydalanuvchiga xabar
    await bot.send_message(user_id, f"✅ #{order_id} buyurtmangiz to‘lovi tasdiqlandi. Tayyorlanmoqda.")
    
    # Adminga yetkazish tugmasi
    deliver_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚚 Yetkazildi", callback_data=f"admin_deliver_{order_id}")]
    ])
    await callback.message.edit_text(f"✅ <b>Buyurtma #{order_id} to‘lovi tasdiqlandi.</b>", parse_mode="HTML", reply_markup=deliver_kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_reject_"))
async def admin_reject(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, status FROM orders WHERE id=?", (order_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            await callback.answer("Buyurtma topilmadi!")
            return
        if row[1] != "toʻlov_kutilmoqda":
            await callback.answer(f"Buyurtma allaqachon {row[1]}!")
            return
        user_id = row[0]
        await db.execute("UPDATE orders SET status='bekor_qilingan' WHERE id=?", (order_id,))
        await db.commit()
    
    # Kanal xabarini yangilash
    await send_or_update_channel_message(order_id, "cancelled")
    
    await bot.send_message(user_id, f"❌ #{order_id} buyurtmangiz to‘lovi rad etildi. Admin bilan bog‘laning.")
    await callback.message.edit_text(f"❌ <b>Buyurtma #{order_id} to‘lovi rad etildi.</b>", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_deliver_"))
async def admin_deliver(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin!", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, status FROM orders WHERE id=?", (order_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            await callback.answer("Buyurtma topilmadi!")
            return
        if row[1] != "qabul_qilingan":
            await callback.answer(f"Buyurtma yetkazib berishga tayyor emas! Hozirgi holat: {row[1]}")
            return
        user_id = row[0]
        await db.execute("UPDATE orders SET status='yetkazilgan' WHERE id=?", (order_id,))
        await db.commit()
    
    # Kanal xabarini yangilash
    await send_or_update_channel_message(order_id, "delivered")
    
    await bot.send_message(user_id, f"✅ #{order_id} buyurtmangiz yetkazildi. Rahmat!")
    await callback.message.edit_text(f"✅ <b>Buyurtma #{order_id} yetkazildi.</b>", parse_mode="HTML")
    await callback.answer()

# ========== FOYDALANUVCHI BUYURTMA TARIXI ==========
@dp.message(lambda msg: msg.text == "📜 Mening buyurtmalarim")
async def my_orders(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, products, total, status, table_number, date 
            FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10
        """, (user_id,)) as cur:
            orders = await cur.fetchall()
    
    if not orders:
        await message.answer("📭 Siz hali buyurtma bermagansiz.")
        return
    
    status_emoji = {
        "toʻlov_kutilmoqda": "⏳",
        "qabul_qilingan": "✅",
        "yetkazilgan": "🚚",
        "bekor_qilingan": "❌"
    }
    
    text = "📜 <b>So‘nggi buyurtmalaringiz</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for oid, prods, total, status, table, date in orders:
        emoji = status_emoji.get(status, "📦")
        date_f = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
        text += f"\n#{oid} | {emoji} {status}\n🪑 {table}-stol | {date_f}\n{prods}\n💰 {total:,} so'm\n"
    
    await message.answer(text, parse_mode="HTML")

# ========== ADMIN MAHSULOT BOSHQARISH ==========
@dp.message(lambda msg: msg.text == "➕ Mahsulot qo'shish" and msg.from_user.id == ADMIN_ID)
async def add_start(message: types.Message, state: FSMContext):
    await message.answer("📦 Mahsulot nomini yuboring:")
    await state.set_state(AddProduct.name)

@dp.message(AddProduct.name)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("💰 Narxini faqat raqam bilan yuboring (masalan: 100000):")
    await state.set_state(AddProduct.price)

@dp.message(AddProduct.price)
async def add_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Iltimos, faqat raqam yuboring! Masalan: 100000")
        return
    await state.update_data(price=int(message.text))
    await message.answer("📁 Kategoriyasini yuboring (nargile/aroma/ichimlik):")
    await state.set_state(AddProduct.category)

@dp.message(AddProduct.category)
async def add_category(message: types.Message, state: FSMContext):
    cat = message.text.strip().lower()
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO products (name, price, category) VALUES (?, ?, ?)", (data['name'], data['price'], cat))
            await db.commit()
            await message.answer(f"✅ <b>{data['name']}</b> qo'shildi!", parse_mode="HTML")
        except:
            await message.answer("❌ Bunday nomli mahsulot allaqachon mavjud.")
    await state.clear()

@dp.message(lambda msg: msg.text == "❌ Mahsulot o'chirish" and msg.from_user.id == ADMIN_ID)
async def delete_start(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM products") as cur:
            prods = await cur.fetchall()
    if not prods:
        await message.answer("Mahsulot yo'q.")
        return
    text = "🗑 O'chirish uchun ID raqamini yuboring:\n\n" + "\n".join([f"ID <b>{pid}</b>: {name}" for pid, name in prods])
    await message.answer(text, parse_mode="HTML")
    await state.set_state(DeleteProduct.pid)

@dp.message(DeleteProduct.pid)
async def delete_pid(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID raqam bo'lishi kerak!")
        return
    pid = int(message.text)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE id=?", (pid,))
        if db.total_changes:
            await db.commit()
            await message.answer(f"✅ ID <b>{pid}</b> o'chirildi.", parse_mode="HTML")
        else:
            await message.answer("❌ Bunday ID topilmadi.")
    await state.clear()

@dp.message(lambda msg: msg.text == "📋 Buyurtmalar" and msg.from_user.id == ADMIN_ID)
async def list_orders(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, user_id, products, total, status, table_number, date 
            FROM orders ORDER BY id DESC LIMIT 20
        """) as cur:
            orders = await cur.fetchall()
    
    if not orders:
        await message.answer("📭 Buyurtmalar yo'q.")
        return
    
    text = "📋 <b>Oxirgi 20 buyurtma</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for oid, uid, prods, total, status, table, date in orders:
        date_f = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
        text += f"\n#{oid} | {status}\n👤 {uid} | 🪑 {table}\n📦 {prods}\n💰 {total:,} so'm\n📅 {date_f}\n"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(lambda msg: msg.text == "📊 Statistika" and msg.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            total_orders = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(total) FROM orders WHERE status='yetkazilgan'") as cur:
            revenue = (await cur.fetchone())[0] or 0
        async with db.execute("SELECT COUNT(*) FROM products") as cur:
            total_products = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='toʻlov_kutilmoqda'") as cur:
            pending = (await cur.fetchone())[0]
    
    await message.answer(
        f"📊 <b>Statistika</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Jami buyurtmalar: <b>{total_orders}</b>\n"
        f"💰 Daromad: <b>{revenue:,}</b> so'm\n"
        f"🍽 Mahsulotlar: <b>{total_products}</b>\n"
        f"⏳ Kutilayotgan: <b>{pending}</b>",
        parse_mode="HTML"
    )

@dp.message(lambda msg: msg.text == "📦 Buyurtma berish")
async def quick_order(message: types.Message):
    await show_cart(message)

@dp.message(Command("cancel"))
async def cancel_order(message: types.Message):
    try:
        order_id = int(message.text.split("_")[1])
    except:
        await message.answer("❌ Ishlatish: /cancel_3828")
        return
    
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT status FROM orders WHERE id=? AND user_id=?", (order_id, user_id)) as cur:
            row = await cur.fetchone()
        if not row:
            await message.answer("❌ Buyurtma topilmadi!")
            return
        if row[0] != "toʻlov_kutilmoqda":
            await message.answer(f"❌ Buyurtma #{order_id} allaqachon {row[0]}. Bekor qilib bo'lmaydi.")
            return
        await db.execute("UPDATE orders SET status='bekor_qilingan' WHERE id=?", (order_id,))
        await db.commit()
    
    await send_or_update_channel_message(order_id, "cancelled")
    await message.answer(f"✅ #{order_id} buyurtmangiz bekor qilindi.")
    await bot.send_message(ADMIN_ID, f"❌ Foydalanuvchi #{user_id} #{order_id} buyurtmani bekor qildi.")

@dp.callback_query(lambda c: c.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()

# ========== ISHGA TUSHIRISH ==========
async def main():
    await init_db()
    print("🤖 AlphaHookah bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
