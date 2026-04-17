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
                    balance_usd REAL DEFAULT 0,
                    total_deposited REAL DEFAULT 0,
                    total_withdrawn REAL DEFAULT 0,
                    referrer_id INTEGER,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS cryptos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    min_deposit REAL DEFAULT 10,
                    multiplier REAL DEFAULT 1.5,
                    wait_hours INTEGER DEFAULT 12,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    crypto_id INTEGER NOT NULL,
                    crypto_symbol TEXT NOT NULL,
                    amount REAL NOT NULL,
                    screenshot_file_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    approved_at TEXT,
                    paid_at TEXT,
                    FOREIGN KEY (crypto_id) REFERENCES cryptos(id)
                );

                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    crypto_symbol TEXT NOT NULL,
                    amount REAL NOT NULL,
                    address TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            conn.execute("INSERT OR IGNORE INTO settings VALUES ('referral_bonus', '5')")
        print("✅ Database tayyor!")

    # ==================== CRYPTOS ====================
    def add_crypto(self, symbol: str, name: str, wallet: str,
                   min_deposit: float, multiplier: float, wait_hours: int) -> bool:
        try:
            with self.get_conn() as conn:
                conn.execute("""
                    INSERT INTO cryptos (symbol, name, wallet_address, min_deposit, multiplier, wait_hours)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (symbol.upper(), name, wallet, min_deposit, multiplier, wait_hours))
            return True
        except sqlite3.IntegrityError:
            return False

    def get_crypto(self, crypto_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM cryptos WHERE id = ?", (crypto_id,)).fetchone()
            return dict(row) if row else None

    def get_all_cryptos(self, only_active: bool = False) -> List[Dict]:
        with self.get_conn() as conn:
            q = "SELECT * FROM cryptos"
            if only_active:
                q += " WHERE is_active = 1"
            q += " ORDER BY id"
            return [dict(r) for r in conn.execute(q).fetchall()]

    def update_crypto(self, crypto_id: int, **kwargs):
        allowed = {'name', 'wallet_address', 'min_deposit', 'multiplier', 'wait_hours', 'is_active'}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [crypto_id]
        with self.get_conn() as conn:
            conn.execute(f"UPDATE cryptos SET {set_clause} WHERE id = ?", values)

    def delete_crypto(self, crypto_id: int):
        with self.get_conn() as conn:
            conn.execute("DELETE FROM cryptos WHERE id = ?", (crypto_id,))

    def toggle_crypto(self, crypto_id: int) -> bool:
        with self.get_conn() as conn:
            row = conn.execute("SELECT is_active FROM cryptos WHERE id = ?", (crypto_id,)).fetchone()
            if not row:
                return False
            new_state = 0 if row['is_active'] else 1
            conn.execute("UPDATE cryptos SET is_active = ? WHERE id = ?", (new_state, crypto_id))
            return bool(new_state)

    # ==================== USERS ====================
    def add_user(self, user_id: int, username: str, full_name: str, referrer_id: Optional[int] = None):
        with self.get_conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, username, full_name, referrer_id)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, full_name, referrer_id))

    def get_user(self, user_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_all_users(self, limit: int = 5000) -> List[Dict]:
        with self.get_conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()]

    def add_balance(self, user_id: int, amount: float):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE users SET balance_usd = balance_usd + ? WHERE user_id = ?",
                (amount, user_id)
            )

    def deduct_balance(self, user_id: int, amount: float):
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE users SET balance_usd = balance_usd - ?,
                total_withdrawn = total_withdrawn + ? WHERE user_id = ?
            """, (amount, amount, user_id))

    # ==================== DEPOSITS ====================
    def create_deposit(self, user_id: int, crypto_id: int, crypto_symbol: str,
                       amount: float, screenshot_file_id: str) -> int:
        with self.get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO deposits (user_id, crypto_id, crypto_symbol, amount, screenshot_file_id)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, crypto_id, crypto_symbol, amount, screenshot_file_id))
            return cursor.lastrowid

    def get_deposit(self, dep_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute("""
                SELECT d.*, c.multiplier, c.wait_hours, c.name as crypto_name
                FROM deposits d JOIN cryptos c ON d.crypto_id = c.id
                WHERE d.id = ?
            """, (dep_id,)).fetchone()
            return dict(row) if row else None

    def approve_deposit(self, dep_id: int):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE deposits SET status = 'approved', approved_at = ? WHERE id = ?
            """, (now, dep_id))
            dep = dict(conn.execute("SELECT * FROM deposits WHERE id = ?", (dep_id,)).fetchone())
            conn.execute("""
                UPDATE users SET total_deposited = total_deposited + ? WHERE user_id = ?
            """, (dep['amount'], dep['user_id']))
            bonus_pct = float(self.get_setting('referral_bonus') or 5) / 100
            user = conn.execute(
                "SELECT referrer_id FROM users WHERE user_id = ?", (dep['user_id'],)
            ).fetchone()
            if user and user['referrer_id']:
                conn.execute(
                    "UPDATE users SET balance_usd = balance_usd + ? WHERE user_id = ?",
                    (dep['amount'] * bonus_pct, user['referrer_id'])
                )

    def reject_deposit(self, dep_id: int):
        with self.get_conn() as conn:
            conn.execute("UPDATE deposits SET status = 'rejected' WHERE id = ?", (dep_id,))

    def mark_paid(self, dep_id: int):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE deposits SET status = 'paid', paid_at = ? WHERE id = ?
            """, (now, dep_id))

    def get_pending_deposits(self) -> List[Dict]:
        with self.get_conn() as conn:
            return [dict(r) for r in conn.execute("""
                SELECT d.*, c.name as crypto_name, c.multiplier, c.wait_hours
                FROM deposits d JOIN cryptos c ON d.crypto_id = c.id
                WHERE d.status = 'pending' ORDER BY d.created_at ASC
            """).fetchall()]

    def get_active_deposits(self, user_id: int) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute("""
                SELECT d.*, c.multiplier, c.wait_hours, c.name as crypto_name
                FROM deposits d JOIN cryptos c ON d.crypto_id = c.id
                WHERE d.user_id = ? AND d.status = 'approved'
            """, (user_id,)).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get('approved_at'):
                    d['approved_at'] = datetime.strptime(d['approved_at'], '%Y-%m-%d %H:%M:%S')
                result.append(d)
            return result

    def get_user_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute("""
                SELECT d.*, c.name as crypto_name, c.multiplier
                FROM deposits d JOIN cryptos c ON d.crypto_id = c.id
                WHERE d.user_id = ? ORDER BY d.created_at DESC LIMIT ?
            """, (user_id, limit)).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get('created_at'):
                    d['created_at'] = datetime.strptime(d['created_at'], '%Y-%m-%d %H:%M:%S')
                result.append(d)
            return result

    # ==================== WITHDRAWALS ====================
    def create_withdrawal(self, user_id: int, crypto_symbol: str, amount: float, address: str):
        with self.get_conn() as conn:
            conn.execute("""
                INSERT INTO withdrawals (user_id, crypto_symbol, amount, address)
                VALUES (?, ?, ?, ?)
            """, (user_id, crypto_symbol, amount, address))

    # ==================== REFERRAL ====================
    def get_referral_count(self, user_id: int) -> int:
        with self.get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)
            ).fetchone()[0]

    def get_referral_earnings(self, user_id: int) -> float:
        bonus_pct = float(self.get_setting('referral_bonus') or 5) / 100
        with self.get_conn() as conn:
            row = conn.execute("""
                SELECT COALESCE(SUM(d.amount), 0)
                FROM deposits d JOIN users u ON d.user_id = u.user_id
                WHERE u.referrer_id = ? AND d.status IN ('approved','paid')
            """, (user_id,)).fetchone()
            return (row[0] or 0) * bonus_pct

    # ==================== SETTINGS ====================
    def get_setting(self, key: str) -> Optional[str]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None

    def set_setting(self, key: str, value: str):
        with self.get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, value))

    # ==================== STATS ====================
    def get_stats(self) -> Dict[str, Any]:
        with self.get_conn() as conn:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_dep = conn.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM deposits
                WHERE status IN ('approved','paid')
            """).fetchone()[0]
            total_paid = conn.execute("""
                SELECT COALESCE(SUM(d.amount * c.multiplier), 0)
                FROM deposits d JOIN cryptos c ON d.crypto_id = c.id
                WHERE d.status = 'paid'
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
                "total_payouts": total_paid,
                "pending": pending,
                "approved": approved,
            }
