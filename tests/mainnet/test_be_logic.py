# -*- coding: utf-8 -*-
import ccxt
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

import config
from live_bot import LiveBot

# 强制开启实盘模式
config.IS_TESTNET = False
config.REAL_TRADING_ENABLED = True

def run_be_test():
    print(f"🚨 [实盘 Mainnet] 开始验证 [自动推保本] 逻辑")
    print("⚠️  警告: 此脚本将消耗真实资金！")
    
    bot = LiveBot()
    symbol = 'BTC/USDT'
    
    try:
        # 1. 开仓 (最小量)
        print("... 开启测试仓位 (LONG 0.002 BTC)")
        # 使用 bot 的方法，但不走完整信号流程，直接调 API
        entry_order = bot.exchange.create_order(symbol, 'MARKET', 'buy', 0.002)
        entry_price = float(entry_order['average'])
        print(f"✅ 已开仓: ${entry_price:.2f}")

        # 2. 挂单
        tp1_price = bot.exchange.price_to_precision(symbol, entry_price + 100)
        tp2_price = bot.exchange.price_to_precision(symbol, entry_price + 200)
        sl_price = bot.exchange.price_to_precision(symbol, entry_price - 100)
        
        tp1 = bot.exchange.create_order(symbol, 'LIMIT', 'sell', 0.001, tp1_price, params={'reduceOnly': True})
        tp2 = bot.exchange.create_order(symbol, 'LIMIT', 'sell', 0.001, tp2_price, params={'reduceOnly': True})
        sl = bot.exchange.create_order(symbol, 'STOP_MARKET', 'sell', 0.002, None, params={'stopPrice': sl_price, 'reduceOnly': True})
        
        print(f"📊 初始状态: TP1=${tp1_price}, TP2=${tp2_price}, SL=${sl_price}")

        # 3. 模拟 TP1 成交 (撤销 TP1)
        print("\n🔥 [模拟] 撤销 TP1 订单以触发推保本...")
        bot.exchange.cancel_order(tp1['id'], symbol)
        
        time.sleep(2)

        # 4. 运行巡检
        print("\n🔍 运行机器人巡检方法...")
        bot.monitor_positions()
        
        # 5. 验证结果
        print("\n⌛️ 正在检查最终挂单状态...")
        time.sleep(2)
        open_orders = bot.exchange.fetch_open_orders(symbol)
        final_sl = next((o for o in open_orders if o['type'].lower() in ['stop', 'stop_market']), None)
        
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
        print("\n🧹 正在清理订单，请手动平仓！")
        # bot.exchange.cancel_all_orders(symbol) # 可选自动清理

if __name__ == "__main__":
    run_be_test()
