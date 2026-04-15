import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    txid TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    approved_at TEXT,
                    paid_at TEXT
                );

                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    address TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );
            """)
            print("✅ Ma'lumotlar bazasi tayyor!")

    # ==================== USERS ====================
    def add_user(self, user_id: int, username: str, full_name: str, referrer_id: Optional[int] = None):
        with self.get_conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, username, full_name, referrer_id)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, full_name, referrer_id))

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
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )

    def deduct_balance(self, user_id: int, amount: float):
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE users
                SET balance = balance - ?,
                    total_withdrawn = total_withdrawn + ?
                WHERE user_id = ?
            """, (amount, amount, user_id))

    # ==================== DEPOSITS ====================
    def create_deposit(self, user_id: int, amount: float, txid: str) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO deposits (user_id, amount, txid)
                VALUES (?, ?, ?)
            """, (user_id, amount, txid))
            return cursor.lastrowid

    def get_deposit(self, dep_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM deposits WHERE id = ?", (dep_id,)
            ).fetchone()
            return dict(row) if row else None

    def approve_deposit(self, dep_id: int):
        with self.get_conn() as conn:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute("""
                UPDATE deposits
                SET status = 'approved', approved_at = ?
                WHERE id = ?
            """, (now, dep_id))

            dep = dict(conn.execute(
                "SELECT * FROM deposits WHERE id = ?", (dep_id,)
            ).fetchone())

            conn.execute("""
                UPDATE users
                SET total_deposited = total_deposited + ?
                WHERE user_id = ?
            """, (dep['amount'], dep['user_id']))

            # Referal bonus 5%
            user_row = conn.execute(
                "SELECT referrer_id FROM users WHERE user_id = ?", (dep['user_id'],)
            ).fetchone()
            if user_row and user_row['referrer_id']:
                bonus = dep['amount'] * 0.05
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
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE deposits
                SET status = 'paid', paid_at = ?
                WHERE id = ?
            """, (now, dep_id))

    def get_active_deposits(self, user_id: int) -> List[Dict]:
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
                    d['approved_at'] = datetime.strptime(d['approved_at'], '%Y-%m-%d %H:%M:%S')
                result.append(d)
            return result

    def get_pending_deposits(self) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM deposits
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """).fetchall()
            return [dict(r) for r in rows]

    def get_user_history(self, user_id: int, limit: int = 10) -> List[Dict]:
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
        with self.get_conn() as conn:
            conn.execute("""
                INSERT INTO withdrawals (user_id, amount, address)
                VALUES (?, ?, ?)
            """, (user_id, amount, address))

    # ==================== REFERRAL ====================
    def get_referral_count(self, user_id: int) -> int:
        with self.get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)
            ).fetchone()[0]

    def get_referral_earnings(self, user_id: int) -> float:
        with self.get_conn() as conn:
            row = conn.execute("""
                SELECT COALESCE(SUM(d.amount * 0.05), 0) as earnings
                FROM deposits d
                JOIN users u ON d.user_id = u.user_id
                WHERE u.referrer_id = ?
                  AND d.status IN ('approved', 'paid')
            """, (user_id,)).fetchone()
            return row[0] if row else 0.0

    # ==================== STATS ====================
    def get_stats(self) -> Dict[str, Any]:
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
            pending = conn.execute(
                "SELECT COUNT(*) FROM deposits WHERE status = 'pending'"
            ).fetchone()[0]
            approved = conn.execute(
                "SELECT COUNT(*) FROM deposits WHERE status = 'approved'"
            ).fetchone()[0]

            return {
                "users": users,
                "total_deposits": total_dep,
                "total_payouts": total_paid * 2,
                "pending": pending,
                "approved": approved
            }
