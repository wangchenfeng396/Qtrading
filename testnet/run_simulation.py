import sys
import os
import importlib

# 1. 路径设置
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '..', 'src')
sys.path.append(src_dir)

# 2. 注入配置 (Magic Step)
# 在导入任何 src 模块之前，先加载本地的 testnet/config.py
# 并将其注册为系统全局的 'config' 模块。
# 这样 src.strategy 和 src.live_bot 导入 config 时，实际上会拿到这个测试网配置。
import config as testnet_config
sys.modules['config'] = testnet_config
sys.modules['src.config'] = testnet_config

print(f"✅ 已加载测试网配置: {testnet_config.__file__}", flush=True)

# 3. 导入核心逻辑
from live_bot import LiveBot
from database import db_testnet # Import testnet DB

class SimulationBot(LiveBot):
    def __init__(self):
        # 1. 注入实盘开启开关，确保 LiveBot 尝试下单
        testnet_config.REAL_TRADING_ENABLED = True
        
        super().__init__()
        
        # 覆盖数据库为测试网库
        self.db = db_testnet
        
        print("⚠️  正在切换至 BINANCE FUTURES TESTNET (手动配置)")
        
        # 2. 手动覆盖 URL 以连接测试网 (绕过 CCXT 的 sandbox 检查)
        self.exchange.urls['api'] = {
            'fapiPublic': 'https://testnet.binancefuture.com/fapi/v1',
            'fapiPrivate': 'https://testnet.binancefuture.com/fapi/v1',
        }
        
        # 3. 强制加载测试网 Key
        if hasattr(testnet_config, 'BINANCE_API_KEY'):
            self.exchange.apiKey = testnet_config.BINANCE_API_KEY
            self.exchange.secret = testnet_config.BINANCE_SECRET
            self.api_ready = True
            print("🔑 测试网 API Key 已配置")
        
        # 重新获取余额以验证连接
        try:
            balance = self.exchange.fetch_balance()
            self.capital = float(balance['USDT']['free'])
            print(f"💰 测试网余额: ${self.capital:.2f}")
        except Exception as e:
            print(f"❌ 测试网连接失败: {e}")

if __name__ == "__main__":
    bot = SimulationBot()
    bot.run()
