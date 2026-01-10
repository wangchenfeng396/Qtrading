# config.py

# --- 账户设置 ---
INITIAL_CAPITAL = 50.0      # 初始资金 (USDT)
LEVERAGE = 5                # 杠杆倍数 (仅用于计算最大可开仓位)
COMMISSION_RATE = 0.0005    # 手续费 (万5, 币安标准)

# --- 风控设置 (严格) ---
# RISK_PER_TRADE_AMOUNT = 0.50 # 固定金额模式 (已弃用)
RISK_PER_TRADE_PCT = 0.02    # 单笔风险: 亏损额不超过本金的 2%

# --- 仓位管理 (资金分配) ---
MAX_OPEN_POSITIONS = 4       # 最大同时持仓数量 (4单)
POSITION_SIZE_PCT = 0.20     # 单笔最大投入资金比例 (20%)
# 逻辑: 每次开仓取 min(风险计算出的仓位, 本金*20%对应的仓位)

SL_PCT = 0.015               # 默认止损幅度 (1.5%) - 如果 ATR 无效
MAX_TRADES_PER_DAY = 5       # 每天最多交易次数
MAX_DAILY_LOSS = -2.00       # 单日最大亏损 (4笔满额止损)
MAX_CONSECUTIVE_LOSS = 4     # 最大连亏次数

# --- 策略选择 ---
ACTIVE_STRATEGY = 'TrendMeanReversion'

# --- 策略参数 (优化版: 趋势+震荡回归) ---
USE_ATR_FOR_SL = True        # 使用 ATR 动态止损
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 2.0      # 止损宽度 = 2.0 * ATR (放宽以防插针)

# 趋势过滤 (1H)
TREND_EMA_PERIOD = 100       # 使用更长周期的 EMA 过滤噪音

# 震荡指标 (5m)
RSI_PERIOD = 14
RSI_OVERSOLD = 35            # 做多阈值 (超卖)
RSI_OVERBOUGHT = 65          # 做空阈值 (超买)

# 布林带 (5m)
BB_PERIOD = 20
BB_STD = 2.0

# --- 止盈策略 ---
TP1_RATIO = 1.5              # 1.5R 减仓
TP1_CLOSE_PCT = 0.5          # 减仓 50%
MOVE_SL_TO_BE_AFTER_TP1 = True 

TP2_RATIO = 3.5              # 3.5R 抓大波段
TP2_CLOSE_PCT = 1.0          

# --- 数据库设置 ---
CLICKHOUSE_HOST = '192.168.66.10'
CLICKHOUSE_PORT = 18123
CLICKHOUSE_USER = 'default'
CLICKHOUSE_PASSWORD = 'uming'
DB_NAME = 'crypto_data'
SOURCE_TABLE = 'btc_usdt_1s'

# --- 消息推送设置 ---
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

NOTIFICATION_ENABLED = True
NOTIFICATION_CHANNELS = ['bk']  # 可选: 'telegram', 'bk'
BARK_URL = os.getenv("BARK_URL", "http://192.168.66.10:10009/myhFXFuNtus7kJHQsBWdzi/")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

# --- 实盘交易设置 (危险操作) ---
REAL_TRADING_ENABLED = False # 设为 True 才会真正下单
IS_TESTNET = False           # 实盘请设为 False

# 币安实盘 API (从环境变量加载)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "YOUR_REAL_API_KEY")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "YOUR_REAL_SECRET")

# --- 网络设置 (代理) ---
# 如果您在中国大陆或其他无法直接访问 Binance 的地区，请设置 HTTP 代理
# 格式示例: "http://127.0.0.1:7890"
PROXY_URL = os.getenv("PROXY_URL", "")  # 设置为空字符串 "" 则不使用代理
#PROXY_URL = "http://192.168.66.6:19091"

