# -*- coding: utf-8 -*-
import ccxt
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

# 加载配置
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

API_KEY = os.getenv("TESTNET_API_KEY")
SECRET = os.getenv("TESTNET_SECRET")
PROXY = os.getenv("PROXY_URL")
SYMBOL = 'BTC/USDT'

def run_sizing_test():
    print(f"🚀 开始测试: 动态仓位计算 (Total Equity vs Available)")
    
    # 1. 初始化
    exchange = ccxt.binance({
        'apiKey': API_KEY, 'secret': SECRET,
        'enableRateLimit': True, 
        'options': {
            'defaultType': 'future',
            'fetchCurrencies': False # 禁用现货账户配置查询
        },
        'verify': False, 
    })
    if PROXY: exchange.proxies = {'http': PROXY, 'https': PROXY}

    # URL Override for Testnet
    testnet_fapi = 'https://testnet.binancefuture.com/fapi/v1'
    testnet_spot = 'https://testnet.binance.vision/api'
    exchange.urls['api'] = {
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
        'dapiPublic': 'https://testnet.binancefuture.com/dapi/v1',
        'dapiPrivate': 'https://testnet.binancefuture.com/dapi/v1',
    }

    try:
        # 2. 获取初始余额
        print("\n[Step 1] 获取初始余额...")
        account = exchange.fapiPrivateV2GetAccount()
        
        usdt_asset = next(a for a in account['assets'] if a['asset'] == 'USDT')
        initial_wallet = float(usdt_asset['walletBalance'])
        initial_available = float(usdt_asset['availableBalance'])
        
        print(f"💰 初始钱包余额 (Total - 不含浮盈): ${initial_wallet:.2f}")
        print(f"💰 初始可用余额 (Free): ${initial_available:.2f}")

        # 3. 模拟下单占用资金
        print("\n[Step 2] 挂一个大额限价单以占用可用余额...")
        # 跳过 load_markets，手动注入精度以避开测试网 API 限制
        exchange.markets = {
            'BTC/USDT': {
                'id': 'BTCUSDT', 'symbol': 'BTC/USDT', 'type': 'future', 'spot': False, 'future': True, 'contract': True,
                'precision': {'amount': 3, 'price': 1},
                'limits': {'amount': {'min': 0.001, 'max': 1000}, 'price': {'min': 0.1, 'max': 1000000}, 'cost': {'min': 5}}
            }
        }
        exchange.precisionMode = ccxt.DECIMAL_PLACES
        
        ticker = exchange.fapiPublicGetTickerPrice({'symbol': 'BTCUSDT'})
        price = float(ticker['price'])
        
        # 格式化价格和数量
        limit_price = price * 0.9
        limit_price_str = exchange.price_to_precision(SYMBOL, limit_price)
        qty_str = exchange.amount_to_precision(SYMBOL, 0.1)
        
        order = exchange.fapiPrivatePostOrder({
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': qty_str,
            'price': limit_price_str
        })
        order_id = order['orderId']
        print(f"✅ 挂单成功 (ID: {order_id})")
        
        time.sleep(2) # 等待同步

        # 4. 再次获取余额
        print("\n[Step 3] 再次获取余额并计算下次开仓量...")
        account_after = exchange.fapiPrivateV2GetAccount()
        usdt_after = next(a for a in account_after['assets'] if a['asset'] == 'USDT')
        
        after_wallet = float(usdt_after['walletBalance'])
        after_available = float(usdt_after['availableBalance'])
        
        print(f"💰 当前钱包余额 (Total): ${after_wallet:.2f} (预期：应与初始接近)")
        print(f"💰 当前可用余额 (Free): ${after_available:.2f} (预期：应减少)")

        # 5. 核心逻辑验证
        # 下单量计算公式: (Capital * 20%) * Leverage / Price
        # 我们希望 Capital = after_wallet
        
        calc_size_original = (initial_wallet * 0.2 * 5) / price
        calc_size_after = (after_wallet * 0.2 * 5) / price
        calc_size_wrong = (after_available * 0.2 * 5) / price
        
        print("\n--- 📊 逻辑验证结果 ---")
        print(f"基于 [初始钱包] 计算的开仓量: {calc_size_original:.5f} BTC")
        print(f"基于 [当前钱包] 计算的开仓量: {calc_size_after:.5f} BTC")
        print(f"基于 [可用余额] 计算的开仓量: {calc_size_wrong:.5f} BTC (不采用)")
        
        if abs(calc_size_after - calc_size_original) < 0.0001:
            print("\n✅ 验证通过！即使资金被占用，下一次下单量依然保持稳定，符合四等分逻辑。")
        else:
            print("\n❌ 验证失败：开仓量发生了大幅波动。")

        # 6. 清理
        print("\n[Step 4] 清理测试挂单...")
        exchange.fapiPrivateDeleteOrder({
            'symbol': 'BTCUSDT',
            'orderId': order_id
        })
        print("✅ 挂单已撤销。")

    except Exception as e:
        print(f"\n❌ 测试异常: {e}")

if __name__ == "__main__":
    run_sizing_test()
