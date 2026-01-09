import ccxt
import os
import time
from dotenv import load_dotenv

# 1. 加载环境变量
load_dotenv()

API_KEY = os.getenv("TESTNET_API_KEY")
SECRET = os.getenv("TESTNET_SECRET")
PROXY = os.getenv("PROXY_URL")

if not API_KEY or not SECRET:
    print("❌ 错误: 未在 .env 文件中找到 TESTNET_API_KEY 或 TESTNET_SECRET")
    exit(1)

def run_test():
    print("--- 开始币安测试网 8x 杠杆及下单测试 ---")

    # 2. 初始化交易所
    exchange_config = {
        'apiKey': API_KEY,
        'secret': SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
        'verify': True,  # 忽略 SSL 验证（防止网络报错）
        #'verify': False,  # 忽略 SSL 验证（防止网络报错）
    }
    
    if PROXY:
        exchange_config['proxies'] = {'http': PROXY, 'https': PROXY}
        print(f"🌐 使用代理: {PROXY}")

    exchange = ccxt.binance(exchange_config)
    
    # 强制覆盖为测试网 URL (覆盖所有可能的端点以防万一)
    # fapi: 合约测试网
    testnet_fapi = 'https://testnet.binancefuture.com/fapi/v1'
    # sapi/spot: 现货测试网 (防止 CCXT 报错缺少 sapi URL)
    testnet_spot = 'https://testnet.binance.vision/api'
    
    exchange.urls['api'] = {
        'fapiPublic': testnet_fapi,
        'fapiPrivate': testnet_fapi,
        'fapiPrivateV2': 'https://testnet.binancefuture.com/fapi/v2', # 指向 V2
        'fapiPublicV2': 'https://testnet.binancefuture.com/fapi/v2',
        'public': testnet_spot,
        'private': testnet_spot,
        'v3': testnet_spot + '/v3',
        'sapi': testnet_spot + '/v3', # 指向现货测试网
        'eapi': testnet_spot + '/v3', 
        'dapiPublic': 'https://testnet.binancefuture.com/dapi/v1',
        'dapiPrivate': 'https://testnet.binancefuture.com/dapi/v1',
    }
    
    symbol = 'BTC/USDT'
    
    try:
        # 3. 测试连接与余额
        # 使用原生接口获取合约账户信息，避免 fetch_balance 自动调用 spot 接口导致 404
        # 对应 endpoint: GET /fapi/v2/account
        account_info = exchange.fapiPrivateV2GetAccount()
        
        usdt_balance = 0.0
        for asset in account_info['assets']:
            if asset['asset'] == 'USDT':
                usdt_balance = float(asset['availableBalance'])
                break
                
        print(f"✅ 连接成功 | 账户余额: ${usdt_balance:.2f}")

        # 4. 设置 8倍 杠杆
        print(f"\n⚡️ 正在设置 {symbol} 杠杆为 8x ...")
        # 使用原生接口 POST /fapi/v1/leverage
        # 注意: 原生接口通常需要移除 '/' 的 symbol (BTCUSDT)
        market_id = symbol.replace('/', '') 
        response = exchange.fapiPrivatePostLeverage({
            'symbol': market_id,
            'leverage': 8
        })
        print(f"✅ 杠杆设置成功: {response['leverage']}x")

        # 5. 执行开仓 (Market Buy)
        quantity = 0.005
        print(f"\n⚡️ 正在市价开多: {quantity} BTC ...")
        
        # POST /fapi/v1/order
        order = exchange.fapiPrivatePostOrder({
            'symbol': market_id,
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': quantity
        })
        print(f"✅ 开仓成功 | 订单ID: {order['orderId']}")
        # 市价单返回可能没有 average 价格，需要用 avgPrice 或自行查询
        # Testnet 模拟撮合可能很快
        entry_price = float(order.get('avgPrice', 0.0))
        if entry_price == 0:
            # 尝试从 cumQuote 计算 (cumQuote / executedQty)
            if float(order['executedQty']) > 0:
                entry_price = float(order['cumQuote']) / float(order['executedQty'])
            else:
                print("⚠️ 无法获取成交均价，假设为当前市价...")
                ticker = exchange.fapiPublicGetTickerPrice({'symbol': market_id})
                entry_price = float(ticker['price'])
        
        print(f"   成交均价: ${entry_price}")
        
        # 6. 计算止盈价格
        tp1_price = int(entry_price * 1.01) # +1%
        tp2_price = int(entry_price * 1.02) # +2%
        
        qty_tp1 = 0.002
        qty_tp2 = 0.003
        
        # 7. 挂止盈单 (TP1)
        print(f"\n⚡️ 正在挂 TP1 ({qty_tp1} BTC @ ${tp1_price}) ...")
        tp1_order = exchange.fapiPrivatePostOrder({
            'symbol': market_id,
            'side': 'SELL',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': qty_tp1,
            'price': tp1_price,
            'reduceOnly': 'true'
        })
        print(f"✅ TP1 挂单成功 | ID: {tp1_order['orderId']}")

        # 8. 挂止盈单 (TP2)
        print(f"⚡️ 正在挂 TP2 ({qty_tp2} BTC @ ${tp2_price}) ...")
        tp2_order = exchange.fapiPrivatePostOrder({
            'symbol': market_id,
            'side': 'SELL',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': qty_tp2,
            'price': tp2_price,
            'reduceOnly': 'true'
        })
        print(f"✅ TP2 挂单成功 | ID: {tp2_order['orderId']}")

        print("\n🎉 测试全部完成！请登录测试网查看持仓。")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")

if __name__ == "__main__":
    run_test()
