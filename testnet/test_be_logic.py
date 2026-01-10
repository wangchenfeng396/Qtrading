# -*- coding: utf-8 -*-
import ccxt
import os
import sys
import time
from dotenv import load_dotenv

# 1. 加载环境变量 (必须在 import src 之前或之后确保正确性)
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 提前提取 Key，防止 NameError
API_KEY = os.getenv("TESTNET_API_KEY")
SECRET = os.getenv("TESTNET_SECRET")
PROXY = os.getenv("PROXY_URL")

import config
from live_bot import LiveBot

# 强制模拟环境
config.IS_TESTNET = True
config.REAL_TRADING_ENABLED = True

class TestBot(LiveBot):
    def __init__(self):
        super().__init__()
        # 强制配置 (再次覆盖以确保一致性)
        testnet_fapi = 'https://testnet.binancefuture.com/fapi/v1'
        self.exchange.urls['api'] = {
            'fapiPublic': testnet_fapi,
            'fapiPrivate': testnet_fapi,
            'fapiPrivateV2': 'https://testnet.binancefuture.com/fapi/v2',
            'fapiPublicV2': 'https://testnet.binancefuture.com/fapi/v2',
            'fapiPrivateV3': 'https://testnet.binancefuture.com/fapi/v3',
            'fapiPublicV3': 'https://testnet.binancefuture.com/fapi/v3',
            'public': testnet_fapi,
            'private': testnet_fapi,
            'v3': testnet_fapi,
            'sapi': testnet_fapi,
            'eapi': testnet_fapi,
        }

def run_be_test():
    if not API_KEY:
        print("❌ 错误: 未找到 TESTNET_API_KEY")
        return

    print("🚀 开始验证 [自动推保本] 逻辑")
    bot = TestBot()
    symbol = 'BTC/USDT'
    
    # 强制标记 API 已就绪
    bot.api_ready = True
    bot.exchange.apiKey = API_KEY
    bot.exchange.secret = SECRET
    
    try:
        # 0. 注入精度信息
        print("... 注入精度信息")
        bot.exchange.markets = {
            symbol: {
                'id': 'BTCUSDT', 'symbol': symbol, 'type': 'future', 'spot': False, 'future': True, 'contract': True,
                'precision': {'amount': 3, 'price': 1},
                'limits': {'amount': {'min': 0.001, 'max': 1000}, 'price': {'min': 0.1, 'max': 1000000}, 'cost': {'min': 5}}
            }
        }
        bot.exchange.precisionMode = ccxt.DECIMAL_PLACES
        
        # 1. 清理环境
        print("... 清理旧订单")
        bot.exchange.fapiPrivateDeleteAllOpenOrders({'symbol': 'BTCUSDT'})
        
        # 2. 开仓
        print("... 开启测试仓位 (LONG 0.005 BTC)")
        entry_order = bot.exchange.fapiPrivatePostOrder({
            'symbol': 'BTCUSDT', 'side': 'BUY', 'type': 'MARKET', 'quantity': '0.005'
        })
        
        entry_price = float(entry_order.get('avgPrice', 0.0))
        if entry_price == 0:
            ticker = bot.exchange.fapiPublicGetTickerPrice({'symbol': 'BTCUSDT'})
            entry_price = float(ticker['price'])
        
        print(f"✅ 已开仓: ${entry_price:.2f}")

        # 3. 设置初始挂单状态 (2 TP + 1 SL)
        tp1_price = bot.exchange.price_to_precision(symbol, entry_price + 200)
        tp2_price = bot.exchange.price_to_precision(symbol, entry_price + 400)
        sl_price = bot.exchange.price_to_precision(symbol, entry_price - 200)
        
        print(f"... 挂出 TP1=${tp1_price}, TP2=${tp2_price}, SL=${sl_price}")
        bot.exchange.fapiPrivatePostOrder({'symbol': 'BTCUSDT', 'side': 'SELL', 'type': 'LIMIT', 'timeInForce': 'GTC', 'quantity': '0.002', 'price': tp1_price, 'reduceOnly': 'true'})
        tp2_order = bot.exchange.fapiPrivatePostOrder({'symbol': 'BTCUSDT', 'side': 'SELL', 'type': 'LIMIT', 'timeInForce': 'GTC', 'quantity': '0.003', 'price': tp2_price, 'reduceOnly': 'true'})
        sl_order = bot.exchange.fapiPrivatePostOrder({'symbol': 'BTCUSDT', 'side': 'SELL', 'type': 'STOP_MARKET', 'stopPrice': sl_price, 'closePosition': 'true'})
        
        # 4. 模拟 TP1 成交 (撤销除 TP2 以外的所有限价单)
        print("\n🔥 [模拟] 撤销 TP1 订单以触发推保本...")
        open_orders = bot.exchange.fetch_open_orders(symbol)
        for o in open_orders:
            if o['type'].lower() == 'limit' and o['id'] != tp2_order['orderId']:
                bot.exchange.cancel_order(o['id'], symbol)
                print(f"🗑 已模拟 TP1 (ID {o['id']}) 离场")
        
        time.sleep(2)

        # 5. 运行机器人巡检方法
        print("\n🔍 运行机器人巡检方法...")
        bot.monitor_positions()
        
        # 6. 验证结果
        print("\n⌛️ 正在检查最终状态...")
        time.sleep(2)
        final_orders = bot.exchange.fetch_open_orders(symbol)
        final_sl = next((o for o in final_orders if o['type'].lower() in ['stop', 'stop_market']), None)
        
        if final_sl:
            final_sl_price = float(final_sl['stopPrice'])
            print(f"🏁 最终止损价: ${final_sl_price:.2f}")
            if abs(final_sl_price - entry_price) < (entry_price * 0.001):
                print("✅ 验证通过！止损已成功移动至保本位。")
            else:
                print(f"❌ 验证失败：止损价 (${final_sl_price}) 不在保本位 (${entry_price})")
        else:
            print("❌ 验证失败：止损单丢失。")

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
    finally:
        print("\n🧹 请记得手动平仓。")

if __name__ == "__main__":
    run_be_test()