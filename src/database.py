import sqlite3
import datetime
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class DBManager:
    def __init__(self, env='live'):
        self.env = env
        db_name = f'trading_history_{env}.db'
        self.db_file = os.path.join(BASE_DIR, db_name)
        self.init_db()

    def get_connection(self):
        # Use check_same_thread=False to allow Flask threads to use the connection
        # Enable WAL mode for better concurrency
        conn = sqlite3.connect(self.db_file, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL;')
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Table for Equity Snapshots (Floating PnL)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS equity_snapshots (
                    timestamp TEXT PRIMARY KEY,
                    total_equity REAL,
                    unrealized_pnl REAL
                )
            ''')
            
            # Table for Trade Operations (Signals/Orders)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    symbol TEXT,
                    side TEXT,
                    action TEXT, 
                    price REAL,
                    quantity REAL,
                    status TEXT,
                    details TEXT
                )
            ''')
            conn.commit()

    def log_equity(self, equity, unrealized=0.0):
        try:
            with self.get_connection() as conn:
                timestamp = datetime.datetime.now().isoformat()
                conn.execute(
                    'INSERT INTO equity_snapshots (timestamp, total_equity, unrealized_pnl) VALUES (?, ?, ?)',
                    (timestamp, equity, unrealized)
                )
                conn.commit()
        except Exception as e:
            print(f"DB Error (log_equity): {e}")

    def log_operation(self, symbol, side, action, price, quantity, status="FILLED", details=""):
        try:
            with self.get_connection() as conn:
                timestamp = datetime.datetime.now().isoformat()
                conn.execute(
                    '''INSERT INTO trade_operations 
                       (timestamp, symbol, side, action, price, quantity, status, details) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (timestamp, symbol, side, action, price, quantity, status, str(details))
                )
                conn.commit()
        except Exception as e:
            print(f"DB Error (log_operation): {e}")

    def get_equity_history(self, limit=1000):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT timestamp, total_equity FROM equity_snapshots ORDER BY timestamp DESC LIMIT ?', (limit,))
                rows = cursor.fetchall()
                # Return reversed (chronological order)
                return rows[::-1]
            except sqlite3.OperationalError:
                return []

    def get_recent_operations(self, limit=50):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT * FROM trade_operations ORDER BY id DESC LIMIT ?', (limit,))
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                return []

# Singleton instances for easy import
db_live = DBManager('live')
db_testnet = DBManager('testnet')

def get_db(env):
    if env == 'live':
        return db_live
    elif env == 'testnet':
        return db_testnet
    return None
