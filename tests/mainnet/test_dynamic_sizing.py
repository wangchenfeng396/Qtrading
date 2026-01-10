# -*- coding: utf-8 -*-
import ccxt
import os
import sys
import time
from dotenv import load_dotenv

# 加载配置
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

import config

def run_sizing_test():
    print(f"🚨 [实盘 Mainnet] 开始测试: 动态仓位计算 (Total Equity vs Available)")
    
    exchange = ccxt.binance({
        'apiKey': config.BINANCE_API_KEY,
        'secret': config.BINANCE_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future', 'fetchCurrencies': False},
    })
    if config.PROXY_URL: exchange.proxies = {'http': config.PROXY_URL, 'https': config.PROXY_URL}

    symbol = 'BTC/USDT'

    try:
        exchange.load_markets() 
        
        # 1. 获取初始余额
        print("\n[Step 1] 获取初始余额...")
        balance = exchange.fetch_balance()
        initial_wallet = float(balance['info']['totalWalletBalance'])
        initial_available = float(balance['info']['availableBalance'])
        
        print(f"💰 初始钱包余额 (Total): ${initial_wallet:.2f}")
        print(f"💰 初始可用余额 (Free): ${initial_available:.2f}")

        # 2. 挂一个远价限价单以占用资金
        ticker = exchange.fetch_ticker(symbol)
        price = float(ticker['last'])
        limit_price = price * 0.5 # 远低于市价
        
        print(f"\n[Step 2] 挂一个限价买单 (0.002 BTC @ ${limit_price:.2f}) 占用资金...")
        order = exchange.create_order(symbol, 'LIMIT', 'buy', 0.002, limit_price, params={'timeInForce': 'GTC'})
        order_id = order['id']
        print(f"✅ 挂单成功 (ID: {order_id})")
        
        time.sleep(2)

        # 3. 再次获取余额
        print("\n[Step 3] 再次获取余额...")
        balance_after = exchange.fetch_balance()
        after_wallet = float(balance_after['info']['totalWalletBalance'])
        after_available = float(balance_after['info']['availableBalance'])
        
        print(f"💰 当前钱包余额 (Total): ${after_wallet:.2f}")
        print(f"💰 当前可用余额 (Free): ${after_available:.2f}")

        # 4. 验证 LiveBot 逻辑
        # LiveBot 使用的是 walletBalance。
        # 只要 after_wallet ≈ initial_wallet，说明计算基准未受挂单影响。
        
        if abs(after_wallet - initial_wallet) < 1.0:
            print("\n✅ 验证通过！WalletBalance 保持稳定，未受挂单影响。")
        else:
            print("\n⚠️  警告：WalletBalance 发生了变化 (可能是资金费率变动)，但只要不剧烈减少即符合预期。")

        if after_available < initial_available:
            print(f"ℹ️  可用余额减少了 ${initial_available - after_available:.2f} (符合预期，被挂单占用)")

        # 5. 撤单
        print("\n[Step 4] 清理测试挂单...")
        exchange.cancel_order(order_id, symbol)
        print("✅ 挂单已撤销。")

    except Exception as e:
        print(f"\n❌ 测试异常: {e}")

if __name__ == "__main__":
    run_sizing_test()
