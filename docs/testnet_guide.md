# 币安模拟盘 (Binance Testnet) 使用指南

## 1. 环境概述
该模块位于 `/testnet` 目录下，专门用于在币安合约测试网（Futures Testnet）上运行策略。它与实盘环境完全隔离，使用虚拟资金进行下单演练。

---

## 2. 核心架构
*   **配置分离**: 使用 `testnet/config.py`，允许设置独立的 API Key、杠杆和本金。
*   **逻辑复用**: 通过 Python 的模块注入技术，它直接运行 `/src` 目录下的核心策略代码，确保“模拟即实盘”。
*   **沙盒模式**: 强制开启 CCXT 的 `set_sandbox_mode(True)`，确保流量只发送至测试网。

---

## 3. 准备工作

### 3.1 获取 API Key
1.  访问 [Binance Futures Testnet](https://testnet.binancefuture.com/) 官网。
2.  使用 GitHub 或 Google 账号登录。
3.  点击 "API Key" 选项卡，生成并记录您的 **API Key** 和 **Secret Key**。
4.  确保您的测试网账户内有模拟资金（通常自带 10,000 USDT）。

### 3.2 配置文件
编辑 `testnet/config.py`：
```python
BINANCE_API_KEY = "您的测试网KEY"
BINANCE_SECRET = "您的测试网SECRET"
BARK_URL = "您的推送地址"
```

---

## 4. 运行模拟盘

在激活虚拟环境后，执行：

```bash
python testnet/run_simulation.py
```

### 预期输出示例：
```text
✅ 已加载测试网配置: .../testnet/config.py
⚠️  已切换至 BINANCE FUTURES TESTNET (模拟盘)
🔑 API Key 已配置
🚀 Qtrading 实盘机器人已启动 | 交易对: BTC/USDT
...
```

---

## 5. 注意事项
1.  **成交价格**: 测试网的深度和成交速度与实盘有所不同，仅用于逻辑验证。
2.  **推送消息**: 信号触发时，消息标题会明确标注为 `SIGNAL`，您可以通过 Bark 实时收到提醒。
3.  **安全性**: 永远不要将实盘的 API Key 填入 `testnet/config.py`。
