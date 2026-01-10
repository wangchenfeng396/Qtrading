import ccxt
import os
import sys
import time
from dotenv import load_dotenv

# 加载配置
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

API_KEY = os.getenv("TESTNET_API_KEY")
SECRET = os.getenv("TESTNET_SECRET")
PROXY = os.getenv("PROXY_URL")

# 参数
SYMBOL = 'BTC/USDT'
POSITION_SIZE_PCT = 0.20
LEVERAGE = 5

def run_cancel_test():
    print(f"🚀 开始测试: 下单 -> 验证资金占用 -> 立即撤单")
    
    # 1. 初始化
    exchange = ccxt.binance({
        'apiKey': API_KEY, 'secret': SECRET,
        'enableRateLimit': True, 'options': {'defaultType': 'future'},
        'verify': False, 
    })
    exchange.precisionMode = ccxt.DECIMAL_PLACES
    if PROXY: exchange.proxies = {'http': PROXY, 'https': PROXY}

    # URL Override
    testnet_fapi = 'https://testnet.binancefuture.com/fapi/v1'
    testnet_spot = 'https://testnet.binance.vision/api'
    exchange.urls = {
        'api': {
            'fapiPublic': testnet_fapi, 'fapiPrivate': testnet_fapi,
            'fapiPrivateV2': 'https://testnet.binancefuture.com/fapi/v2',
            'public': testnet_spot, 'private': testnet_spot, 'v3': testnet_spot+'/v3',
            'sapi': testnet_spot, 'eapi': testnet_spot
        }
    }

    # Mock Market Data
    exchange.markets = {
        'BTC/USDT': {
            'id': 'BTCUSDT', 'symbol': 'BTC/USDT', 'type': 'future', 'spot': False, 'future': True, 'contract': True,
            'precision': {'amount': 3, 'price': 1},
            'limits': {'amount': {'min': 0.001, 'max': 1000}, 'price': {'min': 0.1, 'max': 1000000}, 'cost': {'min': 5}}
        }
    }

    try:
        # 2. 获取余额与价格
        account = exchange.fapiPrivateV2GetAccount()
        capital = 0.0
        for asset in account['assets']:
            if asset['asset'] == 'USDT':
                capital = float(asset['availableBalance'])
                break
        
        ticker = exchange.fapiPublicGetTickerPrice({'symbol': 'BTCUSDT'})
        price = float(ticker['price'])
        print(f"💰 余额: ${capital:.2f} | 市价: ${price:.2f}")

        # 3. 计算 20% 仓位
        target_qty = (capital * POSITION_SIZE_PCT * LEVERAGE) / price
        qty_str = exchange.amount_to_precision(SYMBOL, target_qty)
        print(f"🧮 计划开仓: {qty_str} BTC (占用约 20% 本金)")

        # 4. 下限价单 (挂单，方便撤销)
        # 挂一个远低于市价的买单，确保不成交，方便测试撤单
        limit_price = price * 0.8 
        limit_price_str = exchange.price_to_precision(SYMBOL, limit_price)
        
        print(f"\n⚡️ 挂限价买单 @ ${limit_price_str}...")
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
        
        # 等待订单同步
        time.sleep(2)

        # 5. 查询订单确认
        print("🔍 查询订单状态...")
        check_order = exchange.fapiPrivateGetOrder({
            'symbol': 'BTCUSDT',
            'orderId': order_id
        })
        print(f"   状态: {check_order['status']} | 原量: {check_order['origQty']}")

        # 6. 撤单
        print("\n🗑 正在撤单...")
        exchange.fapiPrivateDeleteOrder({
            'symbol': 'BTCUSDT',
            'orderId': order_id
        })
        print("✅ 撤单成功！资金已释放。")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")

if __name__ == "__main__":
    run_cancel_test()
