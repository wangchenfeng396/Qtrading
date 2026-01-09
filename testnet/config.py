# testnet/config.py (独立配置文件)
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# --- 模拟盘/测试网 专用设置 ---
IS_TESTNET = True           # 标记为测试网环境
REAL_TRADING_ENABLED = True # 模拟盘默认开启交易逻辑

# 从环境变量加载测试网密钥
BINANCE_API_KEY = os.getenv("TESTNET_API_KEY", "YOUR_TESTNET_API_KEY")
BINANCE_SECRET = os.getenv("TESTNET_SECRET", "YOUR_TESTNET_SECRET")

# --- 账户设置 ---
INITIAL_CAPITAL = 1000.0    # 模拟盘初始资金通常较多
LEVERAGE = 5                # 杠杆倍数
COMMISSION_RATE = 0.0005    # 手续费

# --- 风控设置 ---
RISK_PER_TRADE_PCT = 0.02   # 2% 风险
SL_PCT = 0.015
MAX_TRADES_PER_DAY = 10     # 模拟盘可以放宽限制
MAX_DAILY_LOSS = -100.0
MAX_CONSECUTIVE_LOSS = 5

# --- 策略选择 ---
ACTIVE_STRATEGY = 'TrendMeanReversion'

# --- 策略参数 (保持与实盘一致) ---
USE_ATR_FOR_SL = True
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 2.0

# 趋势过滤 (1H)
TREND_EMA_PERIOD = 100

# 震荡指标 (5m)
RSI_PERIOD = 14
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65

# 布林带 (5m)
BB_PERIOD = 20
BB_STD = 2.0

# --- 止盈策略 ---
TP1_RATIO = 1.5
TP1_CLOSE_PCT = 0.5
MOVE_SL_TO_BE_AFTER_TP1 = True 

TP2_RATIO = 3.5
TP2_CLOSE_PCT = 1.0

# --- 其他设置 ---
# 模拟盘不需要连接 ClickHouse
CLICKHOUSE_HOST = ''
CLICKHOUSE_PORT = 8123
CLICKHOUSE_USER = ''
CLICKHOUSE_PASSWORD = ''
DB_NAME = ''
SOURCE_TABLE = ''

# --- 消息推送 ---
NOTIFICATION_ENABLED = True
NOTIFICATION_CHANNELS = ['bk'] 
BARK_URL = os.getenv("BARK_URL", "https://api.day.app/YOUR_KEY/")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

# --- 网络设置 (代理) ---
PROXY_URL = os.getenv("PROXY_URL", "")
