# config.py

# --- 账户设置 ---
INITIAL_CAPITAL = 50.0      # 初始资金 (USDT)
LEVERAGE = 5                # 杠杆倍数 (仅用于计算最大可开仓位)
COMMISSION_RATE = 0.0005    # 手续费 (万5, 币安标准)

# --- 风控设置 (严格) ---
RISK_PER_TRADE_AMOUNT = 0.50 # 单笔亏损金额 ($0.50)
SL_PCT = 0.012               # 默认止损幅度 (1.2%)
MAX_TRADES_PER_DAY = 5       # 每天最多交易次数
MAX_DAILY_LOSS = -1.50       # 单日最大亏损 (达到则停手)
MAX_CONSECUTIVE_LOSS = 3     # 最大连亏次数 (达到则停手)

# --- 止盈策略 ---
TP1_RATIO = 1.0              # 第一止盈位 (R倍数, 1R)
TP1_CLOSE_PCT = 0.5          # 第一止盈平仓比例 (50%)
MOVE_SL_TO_BE_AFTER_TP1 = True # TP1后是否推保本

TP2_RATIO = 2.0              # 第二止盈位 (R倍数, 2R)
TP2_CLOSE_PCT = 1.0          # 第二止盈平仓剩余所有 (100% of remaining)

# --- 数据库设置 ---
CLICKHOUSE_HOST = '192.168.66.10'
CLICKHOUSE_PORT = 18123
CLICKHOUSE_USER = 'default'
CLICKHOUSE_PASSWORD = 'uming'
DB_NAME = 'crypto_data'
SOURCE_TABLE = 'btc_usdt_1s'
