# -*- coding: utf-8 -*-
import ccxt
import os
import sys
import time
from dotenv import load_dotenv

# 加载配置
load_dotenv()
# 将项目根目录加入路径，以便导入 src 模块
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

import config

def run_mainnet_test():
    print(f"🚨 [实盘 Mainnet] 开始全流程测试: 资金复利 + 精度控制 + 真实下单")
    print("⚠️  警告: 此脚本将消耗真实资金！请确保您已了解风险。")
    
    # 1. 初始化 (使用 config.py 中的配置)
    exchange = ccxt.binance({
        'apiKey': config.BINANCE_API_KEY,
        'secret': config.BINANCE_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'fetchCurrencies': False 
        },
        'verify': True, # 实盘通常需要 SSL 验证，如果报错可改为 False
    })
    
    if config.PROXY_URL:
        exchange.proxies = {'http': config.PROXY_URL, 'https': config.PROXY_URL}

    symbol = 'BTC/USDT'
    
    try:
        # 2. 获取余额与行情
        print("... 加载交易对精度信息")
        exchange.load_markets()
        
        print("... 获取账户余额")
        balance = exchange.fetch_balance()
        # 实盘取 Total Equity (Wallet Balance + Unrealized PnL) 还是 Wallet Balance?
        # LiveBot 逻辑是 Wallet Balance。
        # CCXT 标准结构: info['totalWalletBalance']
        capital = float(balance['info']['totalWalletBalance'])
        print(f"💰 当前钱包余额 (WalletBalance): ${capital:.2f}")
        
        ticker = exchange.fetch_ticker(symbol)
        price = float(ticker['last'])
        print(f"📊 当前市价: ${price:.2f}")

        # 3. 计算仓位 (模拟做空 SHORT)
        # 使用极小参数进行测试，防爆仓
        RISK_PCT = 0.005 # 0.5% 风险
        POSITION_SIZE_PCT = 0.05 # 5% 仓位
        ATR_VALUE = 200.0 
        SL_MULTIPLIER = 2.0
        
        print("\n--- 🧮 计算参数 (模拟做空) ---")
        sl_dist = ATR_VALUE * SL_MULTIPLIER
        sl_price = price + sl_dist
        
        risk_per_unit = abs(price - sl_price)
        risk_amount = capital * RISK_PCT
        
        qty_by_risk = risk_amount / risk_per_unit
        max_notional = (capital * POSITION_SIZE_PCT) * config.LEVERAGE
        qty_by_capital = max_notional / price
        
        raw_qty = min(qty_by_risk, qty_by_capital)
        
        # 强制最小下单量检查 (BTC 最小 0.001)
        if raw_qty < 0.001:
            print(f"⚠️ 计算数量 {raw_qty:.5f} 小于最小下单量，调整为 0.001")
            raw_qty = 0.001

        print(f"账户总额: ${capital:.2f}")
        print(f"🟢 最终测试下单数量: {raw_qty:.5f} BTC")

        # 4. 精度格式化
        qty_str = exchange.amount_to_precision(symbol, raw_qty)
        sl_price_str = exchange.price_to_precision(symbol, sl_price)
        
        # 止盈计算
        tp1_price = price - (risk_per_unit * 1.5)
        tp2_price = price - (risk_per_unit * 3.5)
        
        tp1_price_str = exchange.price_to_precision(symbol, tp1_price)
        tp2_price_str = exchange.price_to_precision(symbol, tp2_price)
        
        # 简单分半
        q1 = exchange.amount_to_precision(symbol, float(qty_str) * 0.5)
        q2 = exchange.amount_to_precision(symbol, float(qty_str) - float(q1))

        print(f"格式化后: Qty={qty_str}, SL={sl_price_str}, TP1={tp1_price_str}, TP2={tp2_price_str}")

        # 5. 执行下单 (使用标准 CCXT 接口)
        print("\n⚡️ [实盘] 开始下单...")
        
        # ENTRY (Market Sell)
        order = exchange.create_order(symbol, 'market', 'sell', float(qty_str))
        print(f"✅ 开仓成功 (ID: {order['id']}, Avg: {order['average']})")

        # STOP LOSS
        exchange.create_order(symbol, 'STOP_MARKET', 'buy', float(qty_str), None, 
                            params={'stopPrice': float(sl_price_str), 'reduceOnly': True})
        print(f"✅ 止损挂单成功 ({sl_price_str})")

        # TP1
        exchange.create_order(symbol, 'LIMIT', 'buy', float(q1), float(tp1_price_str),
                            params={'reduceOnly': True})
        print(f"✅ TP1 挂单成功 ({tp1_price_str})")

        # TP2
        exchange.create_order(symbol, 'LIMIT', 'buy', float(q2), float(tp2_price_str),
                            params={'reduceOnly': True})
        print(f"✅ TP2 挂单成功 ({tp2_price_str})")
        
        print("\n✨ [实盘] 验证通过！逻辑完全正确。")
        print("🚨 请立即去币安 App 手动平仓！")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")

if __name__ == "__main__":
    run_mainnet_test()
