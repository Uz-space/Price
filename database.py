import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal, ROUND_HALF_UP
import pytz

# Toshkent vaqt zonasi (UTC+5)
TZ = pytz.timezone('Asia/Tashkent')

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _to_decimal(self, value: float) -> Decimal:
        """Float ni Decimal ga o'tkazish (aniqlik uchun)"""
        return Decimal(str(value))

    def _to_float(self, value: Decimal) -> float:
        """Decimal ni float ga qaytarish"""
        return float(value)

    def _now_tashkent(self) -> str:
        """Toshkent vaqtini string formatda qaytaradi"""
        return datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')

    def create_tables(self):
        with self.get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    balance REAL DEFAULT 0,
                    total_deposited REAL DEFAULT 0,
                    total_withdrawn REAL DEFAULT 0,
                    referrer_id INTEGER,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    txid TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    approved_at TEXT,
                    paid_at TEXT
                );

                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    address TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT
                );
            """)
            print("✅ Ma'lumotlar bazasi tayyor!")

    # ==================== USERS ====================
    def add_user(self, user_id: int, username: str, full_name: str, referrer_id: Optional[int] = None):
        now = self._now_tashkent()
        with self.get_conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, username, full_name, referrer_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, full_name, referrer_id, now))

    def get_user(self, user_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_users(self, limit: int = 20) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def add_balance(self, user_id: int, amount: float):
        """Balansga pul qo'shish (payout uchun)"""
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )

    def deduct_balance(self, user_id: int, amount: float):
        """Balansdan pul yechish"""
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE users
                SET balance = balance - ?,
                    total_withdrawn = total_withdrawn + ?
                WHERE user_id = ?
            """, (amount, amount, user_id))

    # ==================== DEPOSITS ====================
    def create_deposit(self, user_id: int, amount: float, txid: str) -> int:
        now = self._now_tashkent()
        with self.get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO deposits (user_id, amount, txid, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, amount, txid, now))
            return cursor.lastrowid

    def get_deposit(self, dep_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM deposits WHERE id = ?", (dep_id,)
            ).fetchone()
            return dict(row) if row else None

    def approve_deposit(self, dep_id: int):
        """Depozitni tasdiqlash va referal bonus hisoblash"""
        now = self._now_tashkent()
        with self.get_conn() as conn:
            # Depozitni tasdiqlash
            conn.execute("""
                UPDATE deposits
                SET status = 'approved', approved_at = ?
                WHERE id = ?
            """, (now, dep_id))

            # Depozit ma'lumotlarini olish
            dep = dict(conn.execute(
                "SELECT * FROM deposits WHERE id = ?", (dep_id,)
            ).fetchone())

            # Userning total_deposited ni yangilash
            conn.execute("""
                UPDATE users
                SET total_deposited = total_deposited + ?
                WHERE user_id = ?
            """, (dep['amount'], dep['user_id']))

            # Referal bonus 5% (faqat tasdiqlanganda)
            user_row = conn.execute(
                "SELECT referrer_id FROM users WHERE user_id = ?", (dep['user_id'],)
            ).fetchone()
            
            if user_row and user_row['referrer_id']:
                # Decimal bilan hisoblash (aniqlik uchun)
                amount_dec = self._to_decimal(dep['amount'])
                bonus_dec = (amount_dec * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                bonus = self._to_float(bonus_dec)
                
                if bonus > 0:
                    conn.execute(
                        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                        (bonus, user_row['referrer_id'])
                    )

    def reject_deposit(self, dep_id: int):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE deposits SET status = 'rejected' WHERE id = ?", (dep_id,)
            )

    def mark_paid(self, dep_id: int):
        """Depozit bo'yicha to'lov amalga oshirilganini belgilash"""
        now = self._now_tashkent()
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE deposits
                SET status = 'paid', paid_at = ?
                WHERE id = ?
            """, (now, dep_id))

    def get_active_deposits(self, user_id: int) -> List[Dict]:
        """Aktiv (tasdiqlangan ammo to'lanmagan) depozitlar"""
        with self.get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM deposits
                WHERE user_id = ? AND status = 'approved'
                ORDER BY approved_at DESC
            """, (user_id,)).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get('approved_at'):
                    # Stringni datetime obyektiga o'tkazish (Toshkent vaqti bilan)
                    d['approved_at'] = datetime.strptime(d['approved_at'], '%Y-%m-%d %H:%M:%S')
                result.append(d)
            return result

    def get_pending_deposits(self) -> List[Dict]:
        """Kutilayotgan depozitlar"""
        with self.get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM deposits
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """).fetchall()
            return [dict(r) for r in rows]

    def get_user_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Foydalanuvchi tranzaksiya tarixi"""
        with self.get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM deposits
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get('created_at'):
                    d['created_at'] = datetime.strptime(d['created_at'], '%Y-%m-%d %H:%M:%S')
                result.append(d)
            return result

    # ==================== WITHDRAWALS ====================
    def create_withdrawal(self, user_id: int, amount: float, address: str):
        """Yechish so'rovini yaratish"""
        now = self._now_tashkent()
        with self.get_conn() as conn:
            conn.execute("""
                INSERT INTO withdrawals (user_id, amount, address, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, amount, address, now))

    # ==================== REFERRAL ====================
    def get_referral_count(self, user_id: int) -> int:
        """Referal sonini olish"""
        with self.get_conn() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)
            ).fetchone()
            return result[0] if result else 0

    def get_referral_earnings(self, user_id: int) -> float:
        """Referal bonuslardan jami daromad"""
        with self.get_conn() as conn:
            row = conn.execute("""
                SELECT COALESCE(SUM(d.amount * 0.05), 0) as earnings
                FROM deposits d
                JOIN users u ON d.user_id = u.user_id
                WHERE u.referrer_id = ?
                  AND d.status IN ('approved', 'paid')
            """, (user_id,)).fetchone()
            if row and row[0]:
                return round(row[0], 2)
            return 0.0

    # ==================== STATS ====================
    def get_stats(self) -> Dict[str, Any]:
        """Statistika ma'lumotlari (1.2x tizimga mos)"""
        with self.get_conn() as conn:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_dep = conn.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM deposits WHERE status IN ('approved', 'paid')
            """).fetchone()[0]
            total_paid = conn.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM deposits WHERE status = 'paid'
            """).fetchone()[0]
            total_payouts = total_paid * Decimal('1.2')
            pending = conn.execute(
                "SELECT COUNT(*) FROM deposits WHERE status = 'pending'"
            ).fetchone()[0]
            approved = conn.execute(
                "SELECT COUNT(*) FROM deposits WHERE status = 'approved'"
            ).fetchone()[0]

            return {
                "users": users,
                "total_deposits": round(float(total_dep), 2),
                "total_payouts": round(float(total_payouts), 2),
                "pending": pending,
                "approved": approved
            }
