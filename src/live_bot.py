import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import sys
import os

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
import strategy

class LiveBot:
    def __init__(self):
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'} # Use futures market data usually matches spot but good for volume
        })
        self.symbol = 'BTC/USDT'
        self.risk_per_trade = config.RISK_PER_TRADE_AMOUNT
        self.sl_pct = config.SL_PCT
        
    def fetch_candles(self, timeframe, limit=100):
        """Fetch latest candles from Binance"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"❌ Error fetching {timeframe}: {e}")
            return pd.DataFrame()

    def get_latest_indicators(self):
        """Fetch all timeframes and calculate indicators"""
        # 1. Fetch Data
        df_1h = self.fetch_candles('1h')
        df_15m = self.fetch_candles('15m')
        df_5m = self.fetch_candles('5m')

        if df_1h.empty or df_15m.empty or df_5m.empty:
            return None

        # 2. Calculate Indicators (Reusing strategy.py logic manually or via function)
        # Note: strategy.py expects a merged DF, but for live we calculate separately
        
        # 1H Trend
        df_1h['ema50'] = strategy.calculate_ema(df_1h['close'], 50)
        trend_ok = df_1h.iloc[-2]['close'] > df_1h.iloc[-2]['ema50'] # Check closed candle (-2 is last completed)
        
        # 15m Setup
        df_15m['ema20'] = strategy.calculate_ema(df_15m['close'], 20)
        # Pullback condition: Recent 15m closed below EMA20?
        # We check the last closed candle
        pullback_ok = df_15m.iloc[-2]['close'] < df_15m.iloc[-2]['ema20']
        
        # 5m Trigger
        df_5m['ema20'] = strategy.calculate_ema(df_5m['close'], 20)
        
        # Trigger Logic: 
        # Previous closed candle (index -2) was <= EMA
        # Current closed candle (index -1, just finished) is > EMA
        # Note: In live loop, we run just after a candle closes.
        # So df_5m.iloc[-1] is the candle that JUST closed.
        
        current_close = df_5m.iloc[-1]['close']
        current_ema = df_5m.iloc[-1]['ema20']
        prev_close = df_5m.iloc[-2]['close']
        prev_ema = df_5m.iloc[-2]['ema20']
        
        trigger_long = (current_close > current_ema) and (prev_close <= prev_ema)

        return {
            'price': current_close,
            'trend_1h': trend_ok,
            'trend_1h_val': df_1h.iloc[-2]['ema50'],
            'setup_15m': pullback_ok,
            'setup_15m_val': df_15m.iloc[-2]['ema20'],
            'trigger_5m': trigger_long,
            'trigger_val': current_ema
        }

    def calculate_trade_params(self, entry_price):
        sl_dist = entry_price * self.sl_pct
        sl_price = entry_price - sl_dist
        
        risk_per_unit = entry_price - sl_price
        qty = self.risk_per_trade / risk_per_unit
        
        tp1_price = entry_price + (risk_per_unit * config.TP1_RATIO)
        tp2_price = entry_price + (risk_per_unit * config.TP2_RATIO)
        
        return {
            'qty': qty,
            'sl': sl_price,
            'tp1': tp1_price,
            'tp2': tp2_price
        }

    def run(self):
        print(f"🚀 Qtrading Live Bot Started | Symbol: {self.symbol}")
        print(f"Risk: ${self.risk_per_trade} | 1H+15m+5m Strategy")
        print("Waiting for next 5m candle close...\n")

        while True:
            # 1. Sync with time
            now = datetime.now()
            # Calculate seconds until next 5 minute mark (e.g., 10:05, 10:10)
            next_run = now - timedelta(minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond) + timedelta(minutes=5)
            seconds_to_wait = (next_run - now).total_seconds()
            
            # Add a small buffer (e.g., 3 seconds) to ensure exchange has data
            sleep_time = seconds_to_wait + 3
            
            print(f"💤 Sleeping {int(sleep_time)}s until {next_run.strftime('%H:%M:%S')}...")
            time.sleep(sleep_time)
            
            # 2. Execute Logic
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking Market...")
            
            data = self.get_latest_indicators()
            if not data:
                print("⚠️ Data fetch failed, retrying next cycle.")
                continue
                
            # 3. Print Status
            price = data['price']
            status_symbol = "✅" if data['trend_1h'] else "❌"
            setup_symbol = "✅" if data['setup_15m'] else "❌"
            trigger_symbol = "🔥" if data['trigger_5m'] else "Waiting"
            
            print(f"  Price: ${price:.2f}")
            print(f"  1H Trend (> EMA50):  {status_symbol} (EMA: {data['trend_1h_val']:.2f})")
            print(f"  15m Setup (< EMA20): {setup_symbol} (EMA: {data['setup_15m_val']:.2f})")
            print(f"  5m Trigger (Cross):  {trigger_symbol}")

            # 4. Check Signal
            if data['trend_1h'] and data['setup_15m'] and data['trigger_5m']:
                print("\n" + "="*40)
                print(f"🚀 LONG SIGNAL DETECTED!")
                print("="*40)
                
                params = self.calculate_trade_params(price)
                
                print(f"🔵 ENTRY:   ${price:.2f} (Market)")
                print(f"🛑 STOP:    ${params['sl']:.2f} (-1.2%)")
                print(f"🎯 TP1:     ${params['tp1']:.2f} (Sell 50%, Move SL to Entry)")
                print(f"🎯 TP2:     ${params['tp2']:.2f} (Close All)")
                print(f"⚖️ SIZE:    {params['qty']:.5f} BTC")
                print(f"💵 VALUE:   ${params['qty']*price:.2f} (Lev 5x: ${params['qty']*price/5:.2f} Margin)")
                print("="*40 + "\n")
                
                # Optional: Send notification here
            else:
                print("  >> No signal yet.")

if __name__ == "__main__":
    bot = LiveBot()
    bot.run()
