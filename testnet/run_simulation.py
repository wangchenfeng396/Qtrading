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

print(f"✅ 已加载测试网配置: {testnet_config.__file__}")

# 3. 导入核心逻辑
from live_bot import LiveBot

class SimulationBot(LiveBot):
    def __init__(self):
        super().__init__()
        
        # 4. 强制开启测试网模式
        self.exchange.set_sandbox_mode(True)
        print("⚠️  已切换至 BINANCE FUTURES TESTNET (模拟盘)")
        
        # 5. 配置 API Key (下单必需)
        # 如果 config 中没有填，这行可能会报错，提醒用户填写
        if hasattr(testnet_config, 'BINANCE_API_KEY') and testnet_config.BINANCE_API_KEY != "YOUR_TESTNET_API_KEY":
            self.exchange.apiKey = testnet_config.BINANCE_API_KEY
            self.exchange.secret = testnet_config.BINANCE_SECRET
            print("🔑 API Key 已配置")
        else:
            print("⚠️  未配置 API Key，只能获取行情，无法下单。")
            print("   请修改 testnet/config.py 中的 BINANCE_API_KEY")

if __name__ == "__main__":
    bot = SimulationBot()
    bot.run()
