# -*- coding: utf-8 -*-
import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import sys
import os
import requests
import logging
from logging.handlers import TimedRotatingFileHandler

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from strategy_factory import get_strategy
from database import db_live

# --- Logging Setup ---
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logger = logging.getLogger("Qtrading_Live")
logger.setLevel(logging.INFO)

file_handler = TimedRotatingFileHandler(
    os.path.join(log_dir, 'live_bot.log'), when='midnight', interval=1, backupCount=30, encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

logger.addHandler(file_handler)
logger.addHandler(console_handler)

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
            'options': {
                'defaultType': 'future',
                'fetchCurrencies': False  # 关键修复: 禁止获取现货币种信息，防止调用 capital/config/getall 报错
            },
            # 忽略 SSL 证书验证 (解决某些网络环境下的连接问题) 将True改成False
            'verify': True, 
            'timeout': 30000,
        }
        
        if self.api_ready:
            exchange_config['apiKey'] = config.BINANCE_API_KEY
            exchange_config['secret'] = config.BINANCE_SECRET
        
        if config.PROXY_URL and config.PROXY_URL.strip():
            exchange_config['proxies'] = {
                'http': config.PROXY_URL,
                'https': config.PROXY_URL
            }
            logger.info(f"🌐 使用代理: {config.PROXY_URL}")
        else:
            logger.info("🌐 不使用代理 (直连模式)")

        self.exchange = ccxt.binance(exchange_config)
        self.exchange.verify = False
        
        # 显式设置精度模式为 小数位模式 (DECIMAL_PLACES)
        self.exchange.precisionMode = ccxt.DECIMAL_PLACES
        
        # 2. Testnet / Mainnet Mode
        if config.IS_TESTNET:
            # self.exchange.set_sandbox_mode(True) # 禁用
            mode_str = "测试网 (Testnet)"
            logger.warning(f"⚠️  运行模式: {mode_str}")
            
            # 强制覆盖测试网 URL (解决 CCXT 兼容性问题)
            testnet_fapi = 'https://testnet.binancefuture.com/fapi/v1'
            testnet_dapi = 'https://testnet.binancefuture.com/dapi/v1'
            testnet_spot = 'https://testnet.binance.vision/api'
            
            # 必须覆盖所有类型的 endpoint，否则 fetch_ohlcv 内部检查会报错
            self.exchange.urls['api'] = {
                'fapiPublic': testnet_fapi,
                'fapiPrivate': testnet_fapi,
                'fapiPrivateV2': 'https://testnet.binancefuture.com/fapi/v2',
                'fapiPublicV2': 'https://testnet.binancefuture.com/fapi/v2',
                'fapiPrivateV3': 'https://testnet.binancefuture.com/fapi/v3',
                'fapiPublicV3': 'https://testnet.binancefuture.com/fapi/v3',
                
                'dapiPublic': testnet_dapi,
                'dapiPrivate': testnet_dapi,
                
                'public': testnet_spot,
                'private': testnet_spot,
                'v3': testnet_spot, # v3 usually implies /api/v3
                'sapi': testnet_spot, # Margin/Savings
                'eapi': testnet_spot, 
            }
        else:
            mode_str = "实盘 (Mainnet)"
            logger.warning(f"🚨 运行模式: {mode_str}")
            
        self.symbol = 'BTC/USDT'
        self.risk_pct = config.RISK_PER_TRADE_PCT
        self.sl_pct = config.SL_PCT
        
        # 3. Initial Balance Check
        if self.check_connection():
            logger.info(f"✅ 交易所连接正常 | 模式: {mode_str}")
            
            if self.api_ready and config.REAL_TRADING_ENABLED:
                try:
                    if config.IS_TESTNET:
                        # 测试网专用的获取余额方式
                        account_info = self.exchange.fapiPrivateV2GetAccount()
                        for asset in account_info['assets']:
                            if asset['asset'] == 'USDT':
                                # 使用 walletBalance (钱包余额) 而非 availableBalance (可用余额)
                                # 这样可以确保即使有持仓，新开仓位仍按总本金的 20% 计算
                                self.capital = float(asset['walletBalance'])
                                break
                    else:
                        # 实盘使用标准方式
                        balance = self.exchange.fetch_balance()
                        # 使用 total (总权益) 而非 free (可用余额)
                        self.capital = float(balance['USDT']['total'])
                    
                    logger.info(f"💰 账户总权益: ${self.capital:.2f}")
                except Exception as e:
                    logger.error(f"❌ 获取余额失败 (使用默认配置): {e}")
                    self.capital = config.INITIAL_CAPITAL
            elif not self.api_ready:
                logger.info("👀 未配置 API Key，运行在 [行情观察模式]。")
                self.capital = config.INITIAL_CAPITAL
            else:
                logger.info(f"👀 实盘下单已关闭 (REAL_TRADING_ENABLED=False)，仅推送信号。")
                self.capital = config.INITIAL_CAPITAL
                
            self.send_notification("Qtrading 服务启动", f"环境: {mode_str}\n状态: 监控中\n余额: ${self.capital:.2f}")
        else:
            logger.error("❌ 无法连接到币安 API，请检查网络或代理设置。 সন")
            self.send_notification("Qtrading 启动失败", "无法连接交易所 API，正在重试...")
            self.capital = config.INITIAL_CAPITAL

    def check_connection(self):
        try:
            self.exchange.fetch_time()
            return True
        except Exception as e:
            logger.error(f"Connection Error: {e}")
            return False
        
    def send_notification(self, title, message):
        if not config.NOTIFICATION_ENABLED:
            return

        channels = config.NOTIFICATION_CHANNELS
        if isinstance(channels, str):
            channels = [channels]

        if 'bk' in channels and config.BARK_URL:
            try:
                base_url = config.BARK_URL.rstrip('/')
                url = f"{base_url}/{title}/{message}"
                requests.get(url, timeout=5)
            except Exception as e:
                logger.error(f"❌ Bark 推送失败: {e}")

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
                logger.error(f"❌ Telegram 推送失败: {e}")

    def fetch_candles(self, timeframe, limit=100):
        """Fetch latest candles from Binance (using raw endpoint to avoid CCXT routing issues)"""
        try:
            # 使用原生接口 GET /fapi/v1/klines
            # 必须移除 symbol 中的斜杠
            market_id = self.symbol.replace('/', '')
            
            raw_klines = self.exchange.fapiPublicGetKlines({
                'symbol': market_id,
                'interval': timeframe,
                'limit': limit
            })
            
            # 原始数据: [timestamp, open, high, low, close, volume, close_time, ...]
            # 我们只需要前6列
            data = []
            for k in raw_klines:
                data.append([
                    int(k[0]),      # timestamp
                    float(k[1]),    # open
                    float(k[2]),    # high
                    float(k[3]),    # low
                    float(k[4]),    # close
                    float(k[5])     # volume
                ])
            
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
            
        except Exception as e:
            logger.error(f"❌ 获取 {timeframe} K线失败: {e}")
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
        
        # Risk Calculation (Enhanced - U-based)
        if risk_per_unit <= 0:
            qty = 0
        else:
            # 1. Risk Based (USDT)
            risk_amount_usdt = self.capital * self.risk_pct
            qty_by_risk = risk_amount_usdt / risk_per_unit
            
            # 2. Capital Allocation Based (USDT)
            # Max position value = Capital * 20% * Leverage
            max_position_val_usdt = (self.capital * config.POSITION_SIZE_PCT) * config.LEVERAGE
            qty_by_capital = max_position_val_usdt / entry_price
            
            qty = min(qty_by_risk, qty_by_capital)
        
        return {
            'qty': qty,
            'sl': sl_price,
            'tp1': tp1_price,
            'tp2': tp2_price,
            'side': side
        }

    def place_orders(self, side, quantity, price, sl_price, tp1_price, tp2_price):
        """Execute Real Orders on Binance"""
        execution_info = {'success': False}
        try:
            # 确保交易对信息已加载 (用于精度计算)
            if not self.exchange.markets:
                try:
                    self.exchange.load_markets()
                except Exception as e:
                    if config.IS_TESTNET:
                        logger.warning(f"⚠️ load_markets 失败 ({e})，尝试手动注入 BTC/USDT 精度信息...")
                        # 手动注入测试网精度
                        self.exchange.markets = {
                            self.symbol: {
                                'id': 'BTCUSDT',
                                'symbol': self.symbol,
                                'type': 'future',
                                'spot': False,
                                'future': True,
                                'contract': True,
                                'precision': {'amount': 3, 'price': 1},
                                'limits': {'amount': {'min': 0.001, 'max': 1000}, 'price': {'min': 0.1, 'max': 1000000}, 'cost': {'min': 5}}
                            }
                        }
                    else:
                        raise e

            # 格式化精度
            qty_str = self.exchange.amount_to_precision(self.symbol, quantity)
            sl_price_str = self.exchange.price_to_precision(self.symbol, sl_price)
            tp1_price_str = self.exchange.price_to_precision(self.symbol, tp1_price)
            tp2_price_str = self.exchange.price_to_precision(self.symbol, tp2_price)
            
            qty_f = float(qty_str)

            logger.info(f"⚡️ 正在下单: {side} {qty_str} BTC @ 市价")
            
            if not self.api_ready:
                logger.error("❌ 未配置 API Key，无法下单。")
                return execution_info

            # --- Testnet Specific Logic ---
            if config.IS_TESTNET:
                market_id = self.symbol.replace('/', '')
                side_str = 'BUY' if side == 'LONG' else 'SELL'
                sl_side_str = 'SELL' if side == 'LONG' else 'BUY'
                
                # 1. Entry
                entry_order = self.exchange.fapiPrivatePostOrder({
                    'symbol': market_id, 'side': side_str, 'type': 'MARKET', 'quantity': qty_str
                })
                logger.info(f"✅ [Testnet] 开仓成功: {entry_order['orderId']}")
                
                avg_price = float(entry_order.get('avgPrice', 0.0))
                if avg_price == 0: avg_price = price
                
                # 2. SL
                self.exchange.fapiPrivatePostOrder({
                    'symbol': market_id, 'side': sl_side_str, 'type': 'STOP_MARKET',
                    'stopPrice': sl_price_str, 'closePosition': 'true'
                })
                logger.info(f"🛡 [Testnet] 止损已挂单: ${sl_price_str}")
                
                # 3. TP
                qty_tp1 = float(self.exchange.amount_to_precision(self.symbol, qty_f * config.TP1_CLOSE_PCT))
                qty_tp2 = float(self.exchange.amount_to_precision(self.symbol, qty_f - qty_tp1))
                
                if qty_tp1 > 0:
                    self.exchange.fapiPrivatePostOrder({
                        'symbol': market_id, 'side': sl_side_str, 'type': 'LIMIT', 'timeInForce': 'GTC',
                        'quantity': qty_tp1, 'price': tp1_price_str, 'reduceOnly': 'true'
                    })
                
                if qty_tp2 > 0:
                    self.exchange.fapiPrivatePostOrder({
                        'symbol': market_id, 'side': sl_side_str, 'type': 'LIMIT', 'timeInForce': 'GTC',
                        'quantity': qty_tp2, 'price': tp2_price_str, 'reduceOnly': 'true'
                    })
                
                self.db.log_operation(self.symbol, side, 'ENTRY', avg_price, qty_f, 'FILLED')
                
                execution_info = {
                    'success': True,
                    'avg_price': avg_price,
                    'qty': qty_f,
                    'sl_price': float(sl_price_str)
                }
                return execution_info

            # --- Mainnet Logic ---
            order_side = 'buy' if side == 'LONG' else 'sell'
            tp_side = 'sell' if side == 'LONG' else 'buy'
            sl_side = 'sell' if side == 'LONG' else 'buy'
            
            # 1. Entry
            entry_order = self.exchange.create_order(self.symbol, 'market', order_side, qty_f)
            avg_price = entry_order.get('average', price) 
            logger.info(f"✅ 开仓成功: {entry_order['id']}")
            self.db.log_operation(self.symbol, side, 'ENTRY', avg_price, qty_f, 'FILLED')
            
            # 2. SL
            self.exchange.create_order(self.symbol, 'STOP_MARKET', sl_side, qty_f, None, 
                                     params={'stopPrice': float(sl_price_str), 'reduceOnly': True})
            logger.info(f"🛡 止损已挂单: ${sl_price_str}")
            self.db.log_operation(self.symbol, side, 'STOP_LOSS_ORDER', float(sl_price_str), qty_f, 'NEW')

            # 3. TP
            qty_tp1 = float(self.exchange.amount_to_precision(self.symbol, qty_f * config.TP1_CLOSE_PCT))
            qty_tp2 = float(self.exchange.amount_to_precision(self.symbol, qty_f - qty_tp1))
            
            if qty_tp1 > 0:
                self.exchange.create_order(self.symbol, 'limit', tp_side, qty_tp1, float(tp1_price_str), 
                                         params={'reduceOnly': True})
                logger.info(f"💰 TP1 已挂单: ${tp1_price_str}")
                self.db.log_operation(self.symbol, side, 'TP1_ORDER', float(tp1_price_str), qty_tp1, 'NEW')
            
            if qty_tp2 > 0:
                self.exchange.create_order(self.symbol, 'limit', tp_side, qty_tp2, float(tp2_price_str), 
                                         params={'reduceOnly': True})
                logger.info(f"💰 TP2 已挂单: ${tp2_price_str}")
                self.db.log_operation(self.symbol, side, 'TP2_ORDER', float(tp2_price_str), qty_tp2, 'NEW')
            
            execution_info = {
                'success': True,
                'avg_price': avg_price,
                'qty': qty_f,
                'sl_price': float(sl_price_str)
            }
            return execution_info

        except Exception as e:
            logger.error(f"❌ 下单失败: {e}")
            self.db.log_operation(self.symbol, side, 'ERROR', price, quantity, 'FAILED', str(e))
            return {'success': False, 'error': str(e)}

    def update_balance(self):
        """Update wallet balance for position sizing"""
        if not self.api_ready or not config.REAL_TRADING_ENABLED:
            return

        try:
            if config.IS_TESTNET:
                account_info = self.exchange.fapiPrivateV2GetAccount()
                for asset in account_info['assets']:
                    if asset['asset'] == 'USDT':
                        # 使用 walletBalance (纯钱包余额，不含未实现盈亏)
                        self.capital = float(asset['walletBalance'])
                        break
            else:
                balance = self.exchange.fetch_balance()
                # 使用 totalWalletBalance (纯钱包余额)
                # 需确保 balance['info'] 存在且包含该字段 (标准币安合约接口均包含)
                if 'totalWalletBalance' in balance['info']:
                    self.capital = float(balance['info']['totalWalletBalance'])
                else:
                    # Fallback: 如果 info 结构不同，尝试从 assets 列表中查找 USDT
                    for asset in balance['info'].get('assets', []):
                        if asset['asset'] == 'USDT':
                            self.capital = float(asset['walletBalance'])
                            break
                            
        except Exception as e:
            logger.error(f"❌ 更新余额失败: {e}")

    def get_position_data(self):
        """Helper to get current position data safely for both Testnet and Mainnet"""
        try:
            if config.IS_TESTNET:
                # Raw call for Testnet to avoid load_markets issues
                market_id = self.symbol.replace('/', '')
                positions = self.exchange.fapiPrivateV2GetPositionRisk({'symbol': market_id})
                # Result is a list, usually one item for One-Way mode if symbol specified
                if positions:
                    p = positions[0]
                    return {
                        'symbol': self.symbol,
                        'contracts': float(p['positionAmt']),
                        'entryPrice': float(p['entryPrice']),
                        'side': 'long' if float(p['positionAmt']) > 0 else 'short' # Check logic
                    }
                return None
            else:
                # Standard CCXT
                positions = self.exchange.fetch_positions([self.symbol])
                p = next((p for p in positions if p['symbol'] == self.symbol), None)
                if p:
                    return {
                        'symbol': self.symbol,
                        'contracts': float(p['contracts']),
                        'entryPrice': float(p['entryPrice']),
                        'side': p['side']
                    }
                return None
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return None

    def get_open_orders_data(self):
        """Helper to get open orders safely"""
        try:
            if config.IS_TESTNET:
                market_id = self.symbol.replace('/', '')
                raw_orders = self.exchange.fapiPrivateGetOpenOrders({'symbol': market_id})
                orders = []
                for o in raw_orders:
                    orders.append({
                        'id': str(o['orderId']),
                        'type': o['type'], # Raw: LIMIT, STOP_MARKET
                        'stopPrice': float(o.get('stopPrice', 0))
                    })
                return orders
            else:
                # Standard CCXT
                return self.exchange.fetch_open_orders(self.symbol)
        except Exception as e:
            logger.error(f"获取挂单失败: {e}")
            return []

    def monitor_positions(self):
        """订单巡检：实现推保本逻辑 (Move SL to BE)"""
        if not self.api_ready or not config.REAL_TRADING_ENABLED:
            return

        try:
            # 1. 获取当前持仓
            position = self.get_position_data()
            
            if not position or position['contracts'] == 0:
                return # 无持仓

            entry_price = position['entryPrice']
            current_qty = abs(position['contracts'])
            side = 'LONG' if position['contracts'] > 0 else 'SHORT' # positionAmt signed

            # 2. 获取当前挂单
            open_orders = self.get_open_orders_data()
            
            # 分类挂单 (统一转小写进行比较)
            tp_orders = [o for o in open_orders if o['type'].lower() in ['limit', 'take_profit', 'take_profit_market']]
            sl_orders = [o for o in open_orders if o['type'].lower() in ['stop', 'stop_market', 'stop_loss', 'stop_loss_market']]
            
            if len(tp_orders) == 1:
                # 情况 A: 存在旧止损，且还没移动到保本位
                if sl_orders:
                    current_sl_order = sl_orders[0]
                    current_sl_price = float(current_sl_order['stopPrice'])
                    
                    if abs(current_sl_price - entry_price) > (entry_price * 0.001):
                        logger.info(f"🔍 巡检触发: TP1 已成交，正在移动止损至保本位...")
                        self.cancel_and_place_be_sl(side, entry_price, current_qty, current_sl_order['id'])
                
                # 情况 B: 止损单丢失，但仍有持仓且 TP1 已过，补挂保本损
                else:
                    logger.warning(f"⚠️ 巡检警报: 持仓中且 TP1 已过，但未发现止损单！正在补挂保本损...")
                    self.cancel_and_place_be_sl(side, entry_price, current_qty)

        except Exception as e:
            logger.error(f"❌ 订单巡检出错: {e}")

    def cancel_and_place_be_sl(self, side, entry_price, qty, old_order_id=None):
        """撤销旧止损并挂出保本损"""
        try:
            if old_order_id:
                try:
                    self.exchange.cancel_order(old_order_id, self.symbol)
                    logger.info(f"🗑 已撤销旧止损单: {old_order_id}")
                except Exception as e:
                    logger.error(f"⚠️ 撤销旧止损失败 (可能已成交): {e}")

            # 挂新 SL
            sl_side = 'sell' if side == 'LONG' else 'buy'
            be_price_str = self.exchange.price_to_precision(self.symbol, entry_price)
            qty_str = self.exchange.amount_to_precision(self.symbol, qty)
            
            if config.IS_TESTNET:
                market_id = self.symbol.replace('/', '')
                self.exchange.fapiPrivatePostOrder({
                    'symbol': market_id,
                    'side': sl_side.upper(),
                    'type': 'STOP_MARKET',
                    'stopPrice': be_price_str,
                    'closePosition': 'true'
                })
            else:
                self.exchange.create_order(
                    self.symbol, 'STOP_MARKET', sl_side, float(qty_str), None,
                    params={'stopPrice': float(be_price_str), 'reduceOnly': True}
                )
            
            logger.info(f"✅ 保本损挂单成功: ${be_price_str}")
            self.send_notification("🛡 策略更新", f"止损已同步至保本位: ${be_price_str}")
            self.db.log_operation(self.symbol, side, 'MOVE_TO_BE', float(be_price_str), float(qty_str), 'NEW')
            
        except Exception as e:
            logger.error(f"❌ 执行保本损操作失败: {e}")

        except Exception as e:
            logger.error(f"❌ 订单巡检出错: {e}")

    def run(self):
        mode_label = "[模拟盘]" if config.IS_TESTNET else "[实盘]"
        logger.info(f"🚀 {mode_label} Qtrading 机器人已就绪 | 交易对: {self.symbol}")
        logger.info(f"风险设置: {self.risk_pct*100}% 风险/笔 | 仓位上限: {config.POSITION_SIZE_PCT*100}% 资金/笔")
        logger.info(f"当前策略: {config.ACTIVE_STRATEGY}")
        logger.info("等待下一个 5分钟K线 收盘...")

        while True:
            # 1. Update Balance & Log Equity
            self.update_balance()
            self.db.log_equity(self.capital)
            
            # 2. Monitor Positions (推保本)
            self.monitor_positions()

            # 3. Sync with time
            now = datetime.now()
            next_run = now - timedelta(minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond) + timedelta(minutes=5)
            seconds_to_wait = (next_run - now).total_seconds()
            sleep_time = seconds_to_wait + 3
            
            logger.info(f"💤 休眠 {int(sleep_time)}秒 直到 {next_run.strftime('%H:%M:%S')} | 当前权益: ${self.capital:.2f}...")
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
        side_emoji = "🟢" if side == 'LONG' else "🔴"
        
        logger.info("="*40)
        logger.info(f"🚀 {side_cn} 信号触发！")
        logger.info("="*40)
        
        params = self.calculate_trade_params(price, side, atr)
        
        logger.info(f"🔵 开仓价:   ${price:,.2f} (市价)")
        logger.info(f"🛑 止损价:   ${params['sl']:,.2f} (ATR动态)")
        logger.info(f"🎯 止盈一:   ${params['tp1']:,.2f} ({config.TP1_RATIO}R)")
        logger.info(f"🎯 止盈二:   ${params['tp2']:,.2f} ({config.TP2_RATIO}R)")
        logger.info(f"⚖️ 仓位量:   {params['qty']:.5f} BTC")
        logger.info(f"💵 总价值:   ${params['qty']*price:,.2f}")
        
        status_msg = "模拟信号"
        mode_tag = "[模拟]"
        
        # Real Execution
        if config.REAL_TRADING_ENABLED:
            mode_tag = "[实盘]"
            success = self.place_orders(
                side, params['qty'], price, 
                params['sl'], params['tp1'], params['tp2']
            )
            if success:
                status_msg = "下单成功 ✅"
            else:
                status_msg = "下单失败 ❌"
        else:
            logger.info("👀 模拟模式 (未实际下单，请在 config.py 开启 REAL_TRADING_ENABLED")

        logger.info("="*40)
        
        # Enhanced Notification
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg_title = f"{side_emoji} {mode_tag} BTC {side_cn} {status_msg}"
        msg_body = (
            f"⏰ 时间: {current_time}\n"
            f"💰 价格: ${price:,.2f}\n"
            f"🛡 止损: ${params['sl']:,.2f}\n"
            f"🎯 止盈1: ${params['tp1']:,.2f} ({config.TP1_RATIO}R)\n"
            f"🎯 止盈2: ${params['tp2']:,.2f} ({config.TP2_RATIO}R)\n"
            f"⚖️ 仓位: {qty_label}\n"
            f"📊 因子: ATR={atr:.2f}\n"
            f"🤖 策略: {config.ACTIVE_STRATEGY}"
        )
        self.send_notification(msg_title, msg_body)

if __name__ == "__main__":
    bot = LiveBot()
    bot.run()
