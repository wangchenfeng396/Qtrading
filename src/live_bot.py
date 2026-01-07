import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import sys
import os
import requests

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
import strategy

class LiveBot:
    def __init__(self):
        exchange_config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'future'} # Use futures market data usually matches spot but good for volume
        }
        
        # Apply Proxy if configured
        if config.PROXY_URL:
            exchange_config['proxies'] = {
                'http': config.PROXY_URL,
                'https': config.PROXY_URL
            }
            print(f"🌐 Using Proxy: {config.PROXY_URL}")

        self.exchange = ccxt.binance(exchange_config)
        self.symbol = 'BTC/USDT'
        self.risk_pct = config.RISK_PER_TRADE_PCT
        self.sl_pct = config.SL_PCT
        # For live trading, we should ideally fetch balance. 
        # For now, we simulate with config.INITIAL_CAPITAL or a fixed base.
        self.capital = config.INITIAL_CAPITAL 
        
    def send_notification(self, title, message):
        """Send notifications via configured channels (Bark, Telegram)"""
        if not config.NOTIFICATION_ENABLED:
            return

        channels = config.NOTIFICATION_CHANNELS
        if isinstance(channels, str):
            channels = [channels]

        # 1. Bark Notification
        if 'bk' in channels and config.BARK_URL:
            try:
                # Bark format: URL/title/body
                # Ensure URL ends with /
                base_url = config.BARK_URL.rstrip('/')
                # URL encode is handled by requests usually, but direct path construction needs care
                # Better to use POST or GET params
                url = f"{base_url}/{title}/{message}"
                requests.get(url, timeout=5)
                print(f"🔔 Bark notification sent.")
            except Exception as e:
                print(f"❌ Bark notification failed: {e}")

        # 2. Telegram Notification
        if 'tg' in channels and config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
            try:
                tg_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    'chat_id': config.TELEGRAM_CHAT_ID,
                    'text': f"*{title}*\n{message}",
                    'parse_mode': 'Markdown'
                }
                requests.post(tg_url, json=payload, timeout=5)
                print(f"🔔 Telegram notification sent.")
            except Exception as e:
                print(f"❌ Telegram notification failed: {e}")

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
        current_close = df_5m.iloc[-1]['close']
        current_ema = df_5m.iloc[-1]['ema20']
        prev_close = df_5m.iloc[-2]['close']
        prev_ema = df_5m.iloc[-2]['ema20']
        
        # Calculate RSI & ATR (using manual functions from strategy for consistency)
        # Note: We need enough data for ATR period=14. fetch_candles default limit=100 is enough.
        # But strategy.calculate_atr expects a DataFrame.
        df_5m['rsi'] = strategy.calculate_rsi(df_5m['close'], period=config.RSI_PERIOD)
        df_5m['atr'] = strategy.calculate_atr(df_5m, period=config.ATR_PERIOD)
        
        current_rsi = df_5m.iloc[-1]['rsi']
        current_atr = df_5m.iloc[-1]['atr']

        # Long Trigger: Cross Over
        trigger_long = (current_close > current_ema) and (prev_close <= prev_ema)
        # Short Trigger: Cross Under
        trigger_short = (current_close < current_ema) and (prev_close >= prev_ema)
        
        # RSI Filter
        rsi_ok_long = current_rsi < config.RSI_OVERBOUGHT
        rsi_ok_short = current_rsi > config.RSI_OVERSOLD

        return {
            'price': current_close,
            # Long Indicators
            'trend_up': df_1h.iloc[-2]['close'] > df_1h.iloc[-2]['ema50'],
            'setup_long': df_15m.iloc[-2]['close'] < df_15m.iloc[-2]['ema20'],
            'trigger_long': trigger_long,
            'rsi_ok_long': rsi_ok_long,
            
            # Short Indicators
            'trend_down': df_1h.iloc[-2]['close'] < df_1h.iloc[-2]['ema50'],
            'setup_short': df_15m.iloc[-2]['close'] > df_15m.iloc[-2]['ema20'],
            'trigger_short': trigger_short,
            'rsi_ok_short': rsi_ok_short,
            
            # Values for logging
            'ema_1h': df_1h.iloc[-2]['ema50'],
            'ema_15m': df_15m.iloc[-2]['ema20'],
            'ema_5m': current_ema,
            'rsi': current_rsi,
            'atr': current_atr
        }

    def calculate_trade_params(self, entry_price, side='LONG', atr=None):
        if config.USE_ATR_FOR_SL and atr:
            sl_dist = atr * config.ATR_SL_MULTIPLIER
        else:
            sl_dist = entry_price * self.sl_pct
        
        if side == 'LONG':
            sl_price = entry_price - sl_dist
            risk_per_unit = entry_price - sl_price
            tp1_price = entry_price + (risk_per_unit * config.TP1_RATIO)
            tp2_price = entry_price + (risk_per_unit * config.TP2_RATIO)
        else: # SHORT
            sl_price = entry_price + sl_dist
            risk_per_unit = sl_price - entry_price
            tp1_price = entry_price - (risk_per_unit * config.TP1_RATIO)
            tp2_price = entry_price - (risk_per_unit * config.TP2_RATIO)
        
        # Risk Calculation
        risk_amount = self.capital * self.risk_pct
        qty = risk_amount / risk_per_unit
        
        return {
            'qty': qty,
            'sl': sl_price,
            'tp1': tp1_price,
            'tp2': tp2_price,
            'side': side
        }

    def run(self):
        print(f"🚀 Qtrading 实盘机器人已启动 | 交易对: {self.symbol}")
        print(f"风险设置: {self.risk_pct*100}% 资金/笔 (当前本金 ${self.capital}) | 策略: 1H趋势+15m震荡+5m突破 (双向)")
        print(f"过滤条件: RSI<{config.RSI_OVERBOUGHT}(多)/>{config.RSI_OVERSOLD}(空) | 止损: ATR*{config.ATR_SL_MULTIPLIER}")
        print("等待下一个 5分钟K线 收盘...\n")

        while True:
            # 1. Sync with time
            now = datetime.now()
            # Calculate seconds until next 5 minute mark (e.g., 10:05, 10:10)
            next_run = now - timedelta(minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond) + timedelta(minutes=5)
            seconds_to_wait = (next_run - now).total_seconds()
            
            # Add a small buffer (e.g., 3 seconds) to ensure exchange has data
            sleep_time = seconds_to_wait + 3
            
            print(f"💤 休眠 {int(sleep_time)}秒 直到 {next_run.strftime('%H:%M:%S')}...")
            time.sleep(sleep_time)
            
            # 2. Execute Logic
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 正在检查市场...")
            
            data = self.get_latest_indicators()
            if not data:
                print("⚠️ 数据获取失败，将在下一个周期重试。")
                continue
                
            # 3. Print Status
            price = data['price']
            
            # Status Logic
            trend = "多头" if data['trend_up'] else ("空头" if data['trend_down'] else "震荡")
            
            print(f"  价格: ${price:.2f} | RSI: {data['rsi']:.1f} | ATR: {data['atr']:.2f}")
            print(f"  趋势 (1H): {trend} (EMA50: {data['ema_1h']:.2f})")
            
            # Check Long
            if data['trend_up'] and data['setup_long'] and data['trigger_long'] and data['rsi_ok_long']:
                self.execute_signal(price, 'LONG', data['atr'])
            # Check Short
            elif data['trend_down'] and data['setup_short'] and data['trigger_short'] and data['rsi_ok_short']:
                self.execute_signal(price, 'SHORT', data['atr'])
            else:
                print("  >> 暂无信号。")

    def execute_signal(self, price, side, atr):
        side_cn = "做多" if side == 'LONG' else "做空"
        print("\n" + "="*40)
        print(f"🚀 {side_cn} 信号触发！")
        print("="*40)
        
        params = self.calculate_trade_params(price, side, atr)
        
        print(f"🔵 开仓价:   ${price:.2f} (市价)")
        print(f"🛑 止损价:   ${params['sl']:.2f} (ATR动态)")
        print(f"🎯 止盈一:   ${params['tp1']:.2f} ({config.TP1_RATIO}R)")
        print(f"🎯 止盈二:   ${params['tp2']:.2f} ({config.TP2_RATIO}R)")
        print(f"⚖️ 仓位量:   {params['qty']:.5f} BTC")
        print(f"💵 总价值:   ${params['qty']*price:.2f}")
        print("="*40 + "\n")
        
        # Send Notification
        msg_title = f"🚀 BTC/USDT {side_cn} 信号"
        msg_body = (
            f"价格: ${price:.2f}\n"
            f"止损: ${params['sl']:.2f}\n"
            f"TP1: ${params['tp1']:.2f}\n"
            f"TP2: ${params['tp2']:.2f}\n"
            f"仓位: {params['qty']:.5f} BTC"
        )
        self.send_notification(msg_title, msg_body)

if __name__ == "__main__":
    bot = LiveBot()
    bot.run()
