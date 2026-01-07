# strategy.py
import pandas as pd

def calculate_ema(series, span):
    """
    Calculate Exponential Moving Average using Pandas
    """
    return series.ewm(span=span, adjust=False).mean()

def calculate_indicators(df):
    """
    计算技术指标
    输入的是已经 merge 好的大表，包含 1h_close, 15m_close, close (5m) 等
    """
    df = df.copy()
    
    # --- 1H Trend Indicators ---
    # 1H Trend: EMA 50
    df['1h_ema50'] = calculate_ema(df['1h_close'], span=50)
    
    # 15m Setup: EMA 20
    df['15m_ema20'] = calculate_ema(df['15m_close'], span=20)
    
    # 5m Trigger: EMA 20
    df['5m_ema20'] = calculate_ema(df['close'], span=20)
    
    return df

def check_signal(row, prev_row=None):
    """
    检查单根 K 线的信号
    返回: 'LONG', 'SHORT', or None
    """
    if prev_row is None:
        return None

    # --- 1. 1H Trend Filter (Bullish Only for now) ---
    is_trend_up = row['1h_close'] > row['1h_ema50']
    
    if not is_trend_up:
        return None

    # --- 2. 15m Setup (Pullback) ---
    # 逻辑：15m 价格低于 15m EMA20，视为回踩区
    is_pullback = row['15m_close'] < row['15m_ema20']
    
    if not is_pullback:
        return None

    # --- 3. 5m Trigger (Entry) ---
    # 逻辑：5m 收盘价上穿 5m EMA20
    # 当前 > EMA 且 上一根 <= EMA
    trigger_long = (row['close'] > row['5m_ema20']) and (prev_row['close'] <= prev_row['5m_ema20'])
    
    if trigger_long:
        return 'LONG'
    
    return None
