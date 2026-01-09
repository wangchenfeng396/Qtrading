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
from strategy_factory import get_strategy
from database import db_live

# --- Logging Setup ---
# ...

class LiveBot:
    def __init__(self):
        self.db = db_live # Default to live DB
        self.strategy = get_strategy(config.ACTIVE_STRATEGY)
        
        # 1. Exchange Configuration
        self.api_ready = False
        if config.BINANCE_API_KEY and "YOUR_" not in config.BINANCE_API_KEY:
            self.api_ready = True
        
        exchange_config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'future'},
            # 忽略 SSL 证书验证 (解决某些网络环境下的连接问题) 将True改成False
            'verify': True, 
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
        
        # 2. Testnet / Mainnet Mode
        if config.IS_TESTNET:
            self.exchange.set_sandbox_mode(True)
            print("⚠️  运行模式: 测试网 (Testnet)")
            
            # 强制覆盖测试网 URL (解决 CCXT 兼容性问题)
            testnet_fapi = 'https://testnet.binancefuture.com/fapi/v1'
            testnet_spot = 'https://testnet.binance.vision/api'
            self.exchange.urls['api'] = {
                'fapiPublic': testnet_fapi,
                'fapiPrivate': testnet_fapi,
                'fapiPrivateV2': 'https://testnet.binancefuture.com/fapi/v2',
                'fapiPublicV2': 'https://testnet.binancefuture.com/fapi/v2',
                'public': testnet_spot,
                'private': testnet_spot,
                'v3': testnet_spot + '/v3',
                'sapi': testnet_spot + '/v3',
                'eapi': testnet_spot + '/v3',
                'dapiPublic': 'https://testnet.binancefuture.com/dapi/v1',
                'dapiPrivate': 'https://testnet.binancefuture.com/dapi/v1',
            }
        else:
            print("🚨 运行模式: 实盘 (Mainnet)")
            
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

        # Delegate analysis to the active strategy
        return self.strategy.analyze_live(df_1h, df_15m, df_5m)

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
            logger.info(f"⚡️ 正在下单: {side} {quantity:.5f} BTC @ 市价")
            
            if not self.api_ready:
                logger.error("❌ 未配置 API Key，无法下单。")
                return False

            # --- Testnet Specific Logic (Raw Calls for Stability) ---
            if config.IS_TESTNET:
                market_id = self.symbol.replace('/', '')
                side_str = 'BUY' if side == 'LONG' else 'SELL'
                sl_side_str = 'SELL' if side == 'LONG' else 'BUY'
                
                # 1. Entry (Market)
                entry_order = self.exchange.fapiPrivatePostOrder({
                    'symbol': market_id,
                    'side': side_str,
                    'type': 'MARKET',
                    'quantity': quantity
                })
                logger.info(f"✅ [Testnet] 开仓成功: {entry_order['orderId']}")
                
                # Calculate Average Price
                avg_price = float(entry_order.get('avgPrice', 0.0))
                if avg_price == 0 and float(entry_order.get('executedQty', 0)) > 0:
                    avg_price = float(entry_order['cumQuote']) / float(entry_order['executedQty'])
                if avg_price == 0:
                    avg_price = price # Fallback to signal price
                
                # 2. SL (Stop Market)
                self.exchange.fapiPrivatePostOrder({
                    'symbol': market_id,
                    'side': sl_side_str,
                    'type': 'STOP_MARKET',
                    'stopPrice': sl_price,
                    'closePosition': 'true' # ReduceOnly equivalent for Stop Market often needs closePosition or reduceOnly
                })
                logger.info(f"🛡 [Testnet] 止损已挂单: ${sl_price:.2f}")
                
                # 3. TP (Limit)
                qty_tp1 = quantity * config.TP1_CLOSE_PCT
                qty_tp2 = quantity - qty_tp1
                
                # TP1
                self.exchange.fapiPrivatePostOrder({
                    'symbol': market_id,
                    'side': sl_side_str,
                    'type': 'LIMIT',
                    'timeInForce': 'GTC',
                    'quantity': qty_tp1,
                    'price': tp1_price,
                    'reduceOnly': 'true'
                })
                logger.info(f"💰 [Testnet] TP1 已挂单: ${tp1_price:.2f}")
                
                # TP2
                self.exchange.fapiPrivatePostOrder({
                    'symbol': market_id,
                    'side': sl_side_str,
                    'type': 'LIMIT',
                    'timeInForce': 'GTC',
                    'quantity': qty_tp2,
                    'price': tp2_price,
                    'reduceOnly': 'true'
                })
                logger.info(f"💰 [Testnet] TP2 已挂单: ${tp2_price:.2f}")
                
                # Log to DB
                self.db.log_operation(self.symbol, side, 'ENTRY', avg_price, quantity, 'FILLED')
                return True

            # --- Mainnet Logic (Standard CCXT) ---
            order_side = 'buy' if side == 'LONG' else 'sell'
            
            # Entry
            entry_order = self.exchange.create_order(self.symbol, 'market', order_side, quantity)
            avg_price = entry_order.get('average', price) 
            logger.info(f"✅ 开仓成功: {entry_order['id']}")
            self.db.log_operation(self.symbol, side, 'ENTRY', avg_price, quantity, 'FILLED')
            
            # SL
            sl_side = 'sell' if side == 'LONG' else 'buy'
            self.exchange.create_order(
                self.symbol, 'STOP_MARKET', sl_side, quantity, 
                params={'stopPrice': sl_price, 'reduceOnly': True}
            )
            logger.info(f"🛡 止损已挂单: ${sl_price:.2f}")
            self.db.log_operation(self.symbol, side, 'STOP_LOSS_ORDER', sl_price, quantity, 'NEW')

            # TP
            tp_side = 'sell' if side == 'LONG' else 'buy'
            qty_tp1 = quantity * config.TP1_CLOSE_PCT
            qty_tp2 = quantity - qty_tp1
            
            if qty_tp1 > 0:
                self.exchange.create_order(
                    self.symbol, 'LIMIT', tp_side, qty_tp1, tp1_price,
                    params={'reduceOnly': True}
                )
                logger.info(f"💰 TP1 已挂单: ${tp1_price:.2f}")
                self.db.log_operation(self.symbol, side, 'TP1_ORDER', tp1_price, qty_tp1, 'NEW')
            
            if qty_tp2 > 0:
                self.exchange.create_order(
                    self.symbol, 'LIMIT', tp_side, qty_tp2, tp2_price,
                    params={'reduceOnly': True}
                )
                logger.info(f"💰 TP2 已挂单: ${tp2_price:.2f}")
                self.db.log_operation(self.symbol, side, 'TP2_ORDER', tp2_price, qty_tp2, 'NEW')
            
            return True
        except Exception as e:
            logger.error(f"❌ 下单失败: {e}")
            self.db.log_operation(self.symbol, side, 'ERROR', price, quantity, 'FAILED', str(e))
            return False

    def run(self):
        logger.info(f"🚀 Qtrading 实盘机器人已启动 | 交易对: {self.symbol}")
        logger.info(f"风险设置: {self.risk_pct*100}% 资金/笔 (当前本金 ${self.capital:.2f})")
        logger.info(f"当前策略: {config.ACTIVE_STRATEGY}")
        logger.info("等待下一个 5分钟K线 收盘...")

        while True:
            # Log Equity Snapshot
            self.db.log_equity(self.capital)

            # 1. Sync with time
            now = datetime.now()
            next_run = now - timedelta(minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond) + timedelta(minutes=5)
            seconds_to_wait = (next_run - now).total_seconds()
            sleep_time = seconds_to_wait + 3
            
            logger.info(f"💤 休眠 {int(sleep_time)}秒 直到 {next_run.strftime('%H:%M:%S')}...")
            time.sleep(sleep_time)
            
            logger.info("正在检查市场...")
            
            data = self.get_latest_indicators()
            if not data:
                logger.warning("⚠️ 数据获取失败，将在下一个周期重试。")
                continue
                
            # 3. Print Status
            price = data['price']
            indicators = data['indicators']
            signal = data['signal']
            
            logger.info(f"  价格: ${price:.2f} | RSI: {indicators['rsi']:.1f} | ATR: {data['atr']:.2f}")
            logger.info(f"  趋势: {indicators['trend']} (EMA: {indicators['trend_ema']:.2f})")
            
            # Check Signal
            if signal:
                self.execute_signal(price, signal, data['atr'])
            else:
                logger.info("  >> 暂无信号。")

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
