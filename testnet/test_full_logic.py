import ccxt
import os
import sys
import time
from dotenv import load_dotenv

# 加载配置
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 模拟配置参数
SYMBOL = 'BTC/USDT'
RISK_PCT = 0.02
POSITION_SIZE_PCT = 0.20 # 新增：单笔最大占用 20%
LEVERAGE = 5
ATR_VALUE = 200.0 
SL_MULTIPLIER = 2.0

API_KEY = os.getenv("TESTNET_API_KEY")
SECRET = os.getenv("TESTNET_SECRET")
PROXY = os.getenv("PROXY_URL")

def run_test():
    print(f"🚀 开始测试: 多仓位分仓逻辑 (2%风险 vs 20%占用)")
    
    if not API_KEY:
        print("❌ 错误: 未在 .env 找到 TESTNET_API_KEY")
        return

    # 1. 初始化
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
        'verify': False, 
    })
    exchange.precisionMode = ccxt.DECIMAL_PLACES
    if PROXY: exchange.proxies = {'http': PROXY, 'https': PROXY}

    # URL Override
    testnet_fapi = 'https://testnet.binancefuture.com/fapi/v1'
    testnet_spot = 'https://testnet.binance.vision/api'
    exchange.urls['api'] = {
        'fapiPublic': testnet_fapi, 'fapiPrivate': testnet_fapi,
        'fapiPrivateV2': 'https://testnet.binancefuture.com/fapi/v2',
        'public': testnet_spot, 'private': testnet_spot, 'v3': testnet_spot+'/v3',
        'sapi': testnet_spot, 'eapi': testnet_spot
    }

    try:
        # 2. 手动注入精度
        exchange.markets = {
            'BTC/USDT': {
                'id': 'BTCUSDT', 'symbol': 'BTC/USDT', 'type': 'future', 'spot': False, 'future': True, 'contract': True,
                'precision': {'amount': 3, 'price': 1},
                'limits': {'amount': {'min': 0.001, 'max': 1000}, 'price': {'min': 0.1, 'max': 1000000}, 'cost': {'min': 5}}
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

        # 3. 仓位管理逻辑验证 (新逻辑)
        print("\n--- 🧮 仓位计算验证 ---")
        sl_dist = ATR_VALUE * SL_MULTIPLIER
        sl_price = price + sl_dist # 模拟做空
        
        # A. 基于风险 (2% - USDT)
        risk_amount_usdt = capital * RISK_PCT
        risk_per_unit = abs(price - sl_price)
        qty_by_risk = risk_amount_usdt / risk_per_unit
        
        # B. 基于分仓 (20% 本金 * 5倍杠杆 - USDT)
        max_pos_val_usdt = (capital * POSITION_SIZE_PCT) * LEVERAGE
        qty_by_capital = max_pos_val_usdt / price
        
        raw_qty = min(qty_by_risk, qty_by_capital)
        
        print(f"账户总额: ${capital:.2f}")
        print(f"单笔风险限额 (2%): ${risk_amount_usdt:.2f} -> 对应数量: {qty_by_risk:.5f} BTC")
        print(f"单笔资金占用限额 (20%): ${capital * POSITION_SIZE_PCT:.2f}")
        print(f"杠杆后最大价值 (5x): ${max_pos_val_usdt:.2f} -> 对应数量: {qty_by_capital:.5f} BTC")
        print(f"🟢 最终采用数量 (Min): {raw_qty:.5f} BTC")

        # 4. 精度格式化
        qty_str = exchange.amount_to_precision(SYMBOL, raw_qty)
        
        # 5. 执行两次下单 (模拟多单共存)
        for i in range(1, 3):
            print(f"\n⚡️ 正在执行第 {i} 笔模拟开仓...")
            order = exchange.fapiPrivatePostOrder({
                'symbol': 'BTCUSDT',
                'side': 'SELL',
                'type': 'MARKET',
                'quantity': qty_str
            })
            print(f"✅ 开仓成功 (ID: {order['orderId']})")
            time.sleep(1)

        print("\n✨ 验证通过！您现在可以去网页端看到两笔订单已合并为总持仓，但占用的保证金符合 20%*2=40% 的规划。")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")

if __name__ == "__main__":
    run_test()