from .base import BaseStrategy
import indicators
import pandas as pd

class TrendMeanReversion(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.trend_ema_period = config.TREND_EMA_PERIOD
        self.rsi_period = config.RSI_PERIOD
        self.atr_period = config.ATR_PERIOD
        self.bb_period = config.BB_PERIOD
        self.bb_std = config.BB_STD
        self.rsi_overbought = config.RSI_OVERBOUGHT
        self.rsi_oversold = config.RSI_OVERSOLD

    def calculate_indicators(self, df):
        """回测指标计算"""
        df = df.copy()
        # 1H Trend
        df['1h_ema_trend'] = indicators.calculate_ema(df['1h_close'], span=self.trend_ema_period)
        
        # 5m Setup
        df['5m_ema20'] = indicators.calculate_ema(df['close'], span=20)
        df['rsi'] = indicators.calculate_rsi(df['close'], period=self.rsi_period)
        df['atr'] = indicators.calculate_atr(df, period=self.atr_period)
        
        df['bb_upper'], df['bb_lower'] = indicators.calculate_bollinger_bands(
            df['close'], period=self.bb_period, std_dev=self.bb_std
        )
        return df

    def check_signal(self, row, prev_row=None):
        """回测信号判断"""
        if prev_row is None:
            return None

        # Data extraction
        trend_ema = row['1h_ema_trend']
        rsi = row['rsi']
        bb_upper = row['bb_upper']
        bb_lower = row['bb_lower']
        
        is_green = row['close'] > row['open']
        is_red = row['close'] < row['open']

        # LONG Signal
        # 1. 趋势向上 (1H > EMA100)
        # 2. 超卖 (RSI < 35)
        # 3. 触底反弹 (Low <= 下轨 + 收阳)
        if (row['1h_close'] > trend_ema) and \
           (rsi < self.rsi_oversold) and \
           (row['low'] <= bb_lower) and \
           is_green:
            return 'LONG'

        # SHORT Signal
        # 1. 趋势向下 (1H < EMA100)
        # 2. 超买 (RSI > 65)
        # 3. 冲高回落 (High >= 上轨 + 收阴)
        if (row['1h_close'] < trend_ema) and \
           (rsi > self.rsi_overbought) and \
           (row['high'] >= bb_upper) and \
           is_red:
            return 'SHORT'
        
        return None

    def analyze_live(self, df_1h, df_15m, df_5m):
        """实盘实时分析"""
        # 1. Calculate Indicators on separate timeframes
        # 1H
        df_1h['ema_trend'] = indicators.calculate_ema(df_1h['close'], self.trend_ema_period)
        
        # 5m
        df_5m['rsi'] = indicators.calculate_rsi(df_5m['close'], period=self.rsi_period)
        df_5m['atr'] = indicators.calculate_atr(df_5m, period=self.atr_period)
        df_5m['bb_upper'], df_5m['bb_lower'] = indicators.calculate_bollinger_bands(
            df_5m['close'], period=self.bb_period, std_dev=self.bb_std
        )

        # 2. Get Latest Values
        # Note: In LiveBot, we usually check the *closed* candle for confirmation, 
        # or the current developing candle if the strategy allows.
        # This strategy checks for "Close > Open" (Candle Color), so we must look at the 
        # JUST CLOSED candle (iloc[-1] in fetched data usually represents the latest completed or snapshot).
        # Let's assume LiveBot passes data where iloc[-1] is the latest COMPLETED candle.
        
        # Trend (use previous closed 1h candle to be safe/stable)
        trend_val = df_1h.iloc[-2]['ema_trend']
        trend_price = df_1h.iloc[-2]['close']
        
        trend_up = trend_price > trend_val
        trend_down = trend_price < trend_val
        
        # 5m Signals (Latest closed candle)
        row = df_5m.iloc[-1]
        
        current_close = row['close']
        current_open = row['open']
        current_low = row['low']
        current_high = row['high']
        rsi = row['rsi']
        atr = row['atr']
        bb_lower = row['bb_lower']
        bb_upper = row['bb_upper']
        
        is_green = current_close > current_open
        is_red = current_close < current_open
        
        signal = None
        
        # Logic
        if trend_up and (rsi < self.rsi_oversold) and (current_low <= bb_lower) and is_green:
            signal = 'LONG'
        elif trend_down and (rsi > self.rsi_overbought) and (current_high >= bb_upper) and is_red:
            signal = 'SHORT'
            
        trend_str = "多头" if trend_up else "空头"
        
        return {
            'signal': signal,
            'price': current_close,
            'atr': atr,
            'indicators': {
                'rsi': rsi,
                'trend': trend_str,
                'trend_ema': trend_val
            }
        }
