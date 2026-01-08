# -*- coding: utf-8 -*-
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
        # 1. 检查 API 配置
        self.api_ready = False
        if config.BINANCE_API_KEY and "YOUR_" not in config.BINANCE_API_KEY:
            self.api_ready = True
        
        exchange_config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'future'},
            # 忽略 SSL 证书验证 (解决某些网络环境下的连接问题)
            'verify': False, 
            'timeout': 30000,
        }
        
        # 如果有 API Key，加载它
        if self.api_ready:
            exchange_config['apiKey'] = config.BINANCE_API_KEY
            exchange_config['secret'] = config.BINANCE_SECRET
        
        # 2. 代理设置 (仅当配置了非空字符串时才应用)
        if config.PROXY_URL and config.PROXY_URL.strip():
            exchange_config['proxies'] = {
                'http': config.PROXY_URL,
                'https': config.PROXY_URL
            }
            print(f"🌐 使用代理: {config.PROXY_URL}")
        else:
            print("🌐 不使用代理 (直连模式)")

        self.exchange = ccxt.binance(exchange_config)
        
        # 禁止 CCXT 内部的证书验证 (双重保险)
        self.exchange.verify = False
        
        # 3. 运行模式设置
        if config.IS_TESTNET:
            self.exchange.set_sandbox_mode(True)
            mode_str = "测试网 (Testnet)"
        else:
            mode_str = "实盘 (Mainnet)"
            
        self.symbol = 'BTC/USDT'
        self.risk_pct = config.RISK_PER_TRADE_PCT
        self.sl_pct = config.SL_PCT
        self.capital = config.INITIAL_CAPITAL

        # 4. 连接检查与资金获取
        if self.check_connection():
            print(f"✅ 交易所连接正常 | 模式: {mode_str}")
            
            # 尝试获取余额 (仅当 API 配置且非仅行情模式时)
            if self.api_ready and config.REAL_TRADING_ENABLED:
                try:
                    balance = self.exchange.fetch_balance()
                    self.capital = float(balance['USDT']['free'])
                    print(f"💰 账户可用余额: ${self.capital:.2f}")
                except Exception as e:
                    print(f"⚠️ 无法获取余额 (可能权限不足或网络问题): {e}")
                    print(f"   将在默认本金 ${self.capital} 上运行信号逻辑。 সন")
            elif not self.api_ready:
                print("👀 未配置 API Key，运行在 [行情观察模式]。")
            else:
                print(f"👀 实盘下单已关闭 (REAL_TRADING_ENABLED=False)，仅推送信号。 সন")
                
            # 推送启动消息
            self.send_notification("Qtrading 服务启动", f"环境: {mode_str}\n状态: 监控中\n余额: ${self.capital:.2f}")
        else:
            print("❌ 无法连接到币安 API，请检查网络或代理设置。 সন")
            # 即使连接失败也暂不退出，让循环重试
            self.send_notification("Qtrading 启动失败", "无法连接交易所 API，正在重试...")

    def check_connection(self):
        """简单的连通性测试"""
        try:
            self.exchange.fetch_time()
            return True
        except Exception as e:
            print(f"Connection Error: {e}")
            return False
        
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
                base_url = config.BARK_URL.rstrip('/')
                url = f"{base_url}/{title}/{message}"
                requests.get(url, timeout=5)
            except Exception as e:
                print(f"❌ Bark 推送失败: {e}")

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
            except Exception as e:
                print(f"❌ Telegram 推送失败: {e}")

    def fetch_candles(self, timeframe, limit=100):
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"❌ 获取 {timeframe} K线失败: {e}")
            return pd.DataFrame()

    def get_latest_indicators(self):
        df_1h = self.fetch_candles('1h')
        df_15m = self.fetch_candles('15m')
        df_5m = self.fetch_candles('5m')

        if df_1h.empty or df_15m.empty or df_5m.empty:
            return None

        # Calculate Indicators
        df_1h['ema50'] = strategy.calculate_ema(df_1h['close'], config.TREND_EMA_PERIOD)
        df_15m['ema20'] = strategy.calculate_ema(df_15m['close'], 20)
        df_5m['ema20'] = strategy.calculate_ema(df_5m['close'], 20)
        
        current_close = df_5m.iloc[-1]['close']
        
        # RSI & ATR & BB
        df_5m['rsi'] = strategy.calculate_rsi(df_5m['close'], period=config.RSI_PERIOD)
        df_5m['atr'] = strategy.calculate_atr(df_5m, period=config.ATR_PERIOD)
        df_5m['bb_upper'], df_5m['bb_lower'] = strategy.calculate_bollinger_bands(
            df_5m['close'], period=config.BB_PERIOD, std_dev=config.BB_STD
        )
        
        current_rsi = df_5m.iloc[-1]['rsi']
        current_atr = df_5m.iloc[-1]['atr']
        current_low = df_5m.iloc[-1]['low']
        current_high = df_5m.iloc[-1]['high']
        bb_lower = df_5m.iloc[-1]['bb_lower']
        bb_upper = df_5m.iloc[-1]['bb_upper']
        current_open = df_5m.iloc[-1]['open']

        # Logic
        trend_up = df_1h.iloc[-2]['close'] > df_1h.iloc[-2]['ema50']
        trend_down = df_1h.iloc[-2]['close'] < df_1h.iloc[-2]['ema50']
        
        setup_long = (current_rsi < config.RSI_OVERSOLD) and \
                     (current_low <= bb_lower) and \
                     (current_close > current_open)
                     
        setup_short = (current_rsi > config.RSI_OVERBOUGHT) and \
                      (current_high >= bb_upper) and \
                      (current_close < current_open)

        return {
            'price': current_close,
            'trend_up': trend_up,
            'trend_down': trend_down,
            'setup_long': setup_long,
            'setup_short': setup_short,
            'rsi': current_rsi,
            'atr': current_atr,
            'ema_1h': df_1h.iloc[-2]['ema50']
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
        
        qty = (self.capital * self.risk_pct) / risk_per_unit if risk_per_unit > 0 else 0
        
        return {
            'qty': qty,
            'sl': sl_price,
            'tp1': tp1_price,
            'tp2': tp2_price,
            'side': side
        }

    def place_orders(self, side, quantity, price, sl_price, tp1_price, tp2_price):
        """Execute Real Orders on Binance"""
        try:
            print(f"⚡️ 正在下单: {side} {quantity:.5f} BTC @ 市价")
            order_side = 'buy' if side == 'LONG' else 'sell'
            
            if not self.api_ready:
                print("❌ 未配置 API Key，无法下单。 সন")
                return False

            # Entry
            entry_order = self.exchange.create_order(self.symbol, 'market', order_side, quantity)
            print(f"✅ 开仓成功: {entry_order['id']}")
            
            # SL
            sl_side = 'sell' if side == 'LONG' else 'buy'
            self.exchange.create_order(
                self.symbol, 'STOP_MARKET', sl_side, quantity, 
                params={'stopPrice': sl_price, 'reduceOnly': True}
            )
            print(f"🛡 止损已挂单: ${sl_price:.2f}")

            # TP
            tp_side = 'sell' if side == 'LONG' else 'buy'
            qty_tp1 = quantity * config.TP1_CLOSE_PCT
            qty_tp2 = quantity - qty_tp1
            
            if qty_tp1 > 0:
                self.exchange.create_order(
                    self.symbol, 'LIMIT', tp_side, qty_tp1, tp1_price,
                    params={'reduceOnly': True}
                )
            
            if qty_tp2 > 0:
                self.exchange.create_order(
                    self.symbol, 'LIMIT', tp_side, qty_tp2, tp2_price,
                    params={'reduceOnly': True}
                )
            
            return True
        except Exception as e:
            print(f"❌ 下单失败: {e}")
            return False

    def run(self):
        print(f"🚀 Qtrading 实盘机器人已启动 | 交易对: {self.symbol}")
        print(f"风险: {self.risk_pct*100}% | 资金: ${self.capital:.2f} | 策略: 顺势震荡回归 (v2.1)")
        print("等待下一个 5分钟K线 收盘...\n")

        while True:
            now = datetime.now()
            next_run = now - timedelta(minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond) + timedelta(minutes=5)
            seconds_to_wait = (next_run - now).total_seconds()
            sleep_time = seconds_to_wait + 3
            
            print(f"💤 休眠 {int(sleep_time)}秒 直到 {next_run.strftime('%H:%M:%S')}...")
            time.sleep(sleep_time)
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 正在检查市场...")
            
            data = self.get_latest_indicators()
            if not data:
                print("⚠️ 数据获取失败，重试中...")
                continue
                
            price = data['price']
            trend = "多头" if data['trend_up'] else ("空头" if data['trend_down'] else "震荡")
            
            print(f"  价格: ${price:.2f} | RSI: {data['rsi']:.1f} | ATR: {data['atr']:.2f}")
            print(f"  趋势 (1H): {trend} (EMA: {data['ema_1h']:.2f})")
            
            if data['trend_up'] and data['setup_long']:
                self.execute_signal(price, 'LONG', data['atr'])
            elif data['trend_down'] and data['setup_short']:
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
        print(f"🛑 止损价:   ${params['sl']:.2f}")
        print(f"🎯 止盈一:   ${params['tp1']:.2f}")
        print(f"🎯 止盈二:   ${params['tp2']:.2f}")
        print(f"⚖️ 仓位量:   {params['qty']:.5f} BTC")
        
        executed = False
        if config.REAL_TRADING_ENABLED and self.api_ready:
            executed = self.place_orders(side, params['qty'], price, params['sl'], params['tp1'], params['tp2'])
            status_msg = "已自动下单" if executed else "下单失败"
        else:
            status_msg = "模拟信号 (未下单)"
            if not self.api_ready:
                print("⚠️  提示: 未配置 API Key，无法下单。 সন")
            elif not config.REAL_TRADING_ENABLED:
                print("⚠️  提示: 实盘开关未开启 (REAL_TRADING_ENABLED=False)。 সন")

        print("="*40 + "\n")
        
        msg_title = f"🚀 BTC/USDT {side_cn} {status_msg}"
        msg_body = (
            f"价格: ${price:.2f}\n"
            f"止损: ${params['sl']:.2f}\n"
            f"TP1: ${params['tp1']:.2f}\n"
            f"TP2: ${params['tp2']:.2f}\n"
            f"仓位: {params['qty']:.5f} BTC\n"
            f"操作: 请手动挂单或检查自动下单结果"
        )
        self.send_notification(msg_title, msg_body)

if __name__ == "__main__":
    bot = LiveBot()
    bot.run()
