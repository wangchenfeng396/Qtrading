import pandas as pd
import config

def calculate_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=period).mean()

def calculate_bollinger_bands(series, period=20, std_dev=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, lower

def calculate_indicators(df):
    """
    计算技术指标
    """
    df = df.copy()
    
    # --- 1H Trend Indicators ---
    # 使用更长周期的 EMA 判断大趋势
    df['1h_ema_trend'] = calculate_ema(df['1h_close'], span=config.TREND_EMA_PERIOD)
    
    # --- 15m Indicators (辅助) ---
    df['15m_ema20'] = calculate_ema(df['15m_close'], span=20)
    
    # --- 5m Indicators (执行层) ---
    df['5m_ema20'] = calculate_ema(df['close'], span=20)
    
    # RSI & ATR
    df['rsi'] = calculate_rsi(df['close'], period=config.RSI_PERIOD)
    df['atr'] = calculate_atr(df, period=config.ATR_PERIOD)
    
    # Bollinger Bands (5m)
    df['bb_upper'], df['bb_lower'] = calculate_bollinger_bands(
        df['close'], period=config.BB_PERIOD, std_dev=config.BB_STD
    )
    
    return df

def check_signal(row, prev_row=None):
    """
    检查单根 K 线的信号
    策略: 顺势 + 震荡回归 (Mean Reversion in Trend)
    """
    if prev_row is None:
        return None

    # --- Indicators ---
    # Trend
    trend_ema = row['1h_ema_trend']
    
    # 5m Setup
    rsi = row['rsi']
    bb_upper = row['bb_upper']
    bb_lower = row['bb_lower']
    
    # Candle Color
    is_green = row['close'] > row['open']
    is_red = row['close'] < row['open']

    # --- LONG Signal ---
    # 1. 趋势向上 (1H Close > EMA 100)
    # 2. 超卖 (RSI < 35)
    # 3. 触底反弹 (最低价触及下轨 + 收阳线)
    if (row['1h_close'] > trend_ema) and \
       (rsi < config.RSI_OVERSOLD) and \
       (row['low'] <= bb_lower) and \
       is_green:
        return 'LONG'

    # --- SHORT Signal ---
    # 1. 趋势向下 (1H Close < EMA 100)
    # 2. 超买 (RSI > 65)
    # 3. 冲高回落 (最高价触及上轨 + 收阴线)
    if (row['1h_close'] < trend_ema) and \
       (rsi > config.RSI_OVERBOUGHT) and \
       (row['high'] >= bb_upper) and \
       is_red:
        return 'SHORT'
    
    return None
