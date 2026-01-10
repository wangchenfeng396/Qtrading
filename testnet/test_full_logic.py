import ccxt
import os
import sys
from dotenv import load_dotenv

# 加载配置
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 模拟配置参数
SYMBOL = 'BTC/USDT'
RISK_PCT = 0.02
ATR_VALUE = 200.0 # 假设 ATR 为 200
SL_MULTIPLIER = 2.0

API_KEY = os.getenv("TESTNET_API_KEY")
SECRET = os.getenv("TESTNET_SECRET")
PROXY = os.getenv("PROXY_URL")

if not API_KEY:
    print("❌ 错误: 未找到 TESTNET_API_KEY")
    exit(1)

def run_test():
    print(f"🚀 开始测试: 资金复利计算 + 精度控制 + 真实下单")
    
    # 1. 初始化
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
        'verify': False, 
    })
    
    # 显式设置精度模式为 小数位模式 (DECIMAL_PLACES)
    exchange.precisionMode = ccxt.DECIMAL_PLACES
    
    if PROXY:
        exchange.proxies = {'http': PROXY, 'https': PROXY}

    # URL Override (Full coverage to satisfy CCXT validation)
    testnet_fapi = 'https://testnet.binancefuture.com/fapi/v1'
    testnet_spot = 'https://testnet.binance.vision/api'
    
    exchange.urls['api'] = {
        'fapiPublic': testnet_fapi,
        'fapiPrivate': testnet_fapi,
        'fapiPrivateV2': 'https://testnet.binancefuture.com/fapi/v2',
        'fapiPublicV2': 'https://testnet.binancefuture.com/fapi/v2',
        'fapiPrivateV3': 'https://testnet.binancefuture.com/fapi/v3',
        'fapiPublicV3': 'https://testnet.binancefuture.com/fapi/v3',
        
        'public': testnet_spot,
        'private': testnet_spot,
        'v3': testnet_spot + '/v3',
        'sapi': testnet_spot + '/v3', 
        'eapi': testnet_spot + '/v3',
        
        'dapiPublic': 'https://testnet.binancefuture.com/dapi/v1',
        'dapiPrivate': 'https://testnet.binancefuture.com/dapi/v1',
    }

    try:
        # 2. 获取余额与行情
        print("... (跳过 load_markets，手动注入精度信息以避开测试网 API 限制)")
        # 手动注入 BTC/USDT 精度信息
        exchange.markets = {
            'BTC/USDT': {
                'id': 'BTCUSDT',
                'symbol': 'BTC/USDT',
                'type': 'future',
                'spot': False,
                'future': True,
                'contract': True,
                'precision': {
                    'amount': 3,
                    'price': 1
                },
                'limits': {
                    'amount': {'min': 0.001, 'max': 1000},
                    'price': {'min': 0.1, 'max': 1000000},
                    'cost': {'min': 5}
                }
            }
        }
        
        print("... 获取账户余额")
        account = exchange.fapiPrivateV2GetAccount()
        capital = 0.0
        for asset in account['assets']:
            if asset['asset'] == 'USDT':
                capital = float(asset['availableBalance'])
                break
        
        print(f"💰 当前余额: ${capital:.2f}")
        
        ticker = exchange.fapiPublicGetTickerPrice({'symbol': 'BTCUSDT'})
        price = float(ticker['price'])
        print(f"📊 当前市价: ${price:.2f}")

        # 3. 复利仓位计算 (模拟做空 SHORT)
        print("\n--- 🧮 计算参数 (模拟做空) ---")
        sl_dist = ATR_VALUE * SL_MULTIPLIER
        sl_price = price + sl_dist # 做空止损在上方
        
        risk_per_unit = abs(price - sl_price)
        risk_amount = capital * RISK_PCT
        
        raw_qty = risk_amount / risk_per_unit
        
        # 4. 精度格式化 (关键修复点)
        qty_str = exchange.amount_to_precision(SYMBOL, raw_qty)
        sl_price_str = exchange.price_to_precision(SYMBOL, sl_price)
        
        # 止盈计算
        tp1_price = price - (risk_per_unit * 1.5)
        tp2_price = price - (risk_per_unit * 3.5)
        
        tp1_price_str = exchange.price_to_precision(SYMBOL, tp1_price)
        tp2_price_str = exchange.price_to_precision(SYMBOL, tp2_price)
        
        q1 = exchange.amount_to_precision(SYMBOL, float(qty_str) * 0.5)
        q2 = exchange.amount_to_precision(SYMBOL, float(qty_str) - float(q1))

        print(f"原始数量: {raw_qty} -> 格式化后: {qty_str}")
        print(f"止损价格: {sl_price} -> 格式化后: {sl_price_str}")
        print(f"TP1: {tp1_price_str} (Qty: {q1})")
        print(f"TP2: {tp2_price_str} (Qty: {q2})")

        # 5. 执行下单
        print("\n⚡️ 开始下单...")
        
        # ENTRY (Market Sell)
        order = exchange.fapiPrivatePostOrder({
            'symbol': 'BTCUSDT',
            'side': 'SELL',
            'type': 'MARKET',
            'quantity': qty_str
        })
        print(f"✅ 开仓成功 (ID: {order['orderId']})")

        # STOP LOSS
        exchange.fapiPrivatePostOrder({
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'type': 'STOP_MARKET',
            'stopPrice': sl_price_str,
            'closePosition': 'true'
        })
        print(f"✅ 止损挂单成功 ({sl_price_str})")

        # TP1
        exchange.fapiPrivatePostOrder({
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': q1,
            'price': tp1_price_str,
            'reduceOnly': 'true'
        })
        print(f"✅ TP1 挂单成功 ({tp1_price_str})")

        # TP2
        exchange.fapiPrivatePostOrder({
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': q2,
            'price': tp2_price_str,
            'reduceOnly': 'true'
        })
        print(f"✅ TP2 挂单成功 ({tp2_price_str})")
        
        print("\n✨ 验证通过！逻辑完全正确。请去网页平仓。")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")

if __name__ == "__main__":
    run_test()
