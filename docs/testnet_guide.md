# 币安模拟盘 (Testnet) 深度指南

## 1. 核心机制：原生接口调用
由于币安合约测试网 (Binance Futures Testnet) 的特殊性，标准的 CCXT 封装可能会遇到 URL 路由错误或功能受限（如 "sandbox mode not supported"）。

本系统采用了 **Hybrid 模式** 解决此问题：
*   **实盘**: 使用标准的 `ccxt.create_order`，稳定可靠。
*   **测试网**: 使用 `fapiPrivatePostOrder` 等**原生隐式接口**，并配合手动 URL 映射。

这一机制在 `src/live_bot.py` 中自动处理，用户**无需**关心底层差异。

## 2. 常见问题排查

### 2.1 报错: `Precision is over the maximum` (-1111)
*   **原因**: 下单数量或价格的小数位数超过了交易所限制。
*   **解决**: 系统已内置自动精度对齐 (`amount_to_precision`)。请确保不要修改 `live_bot.py` 中的格式化逻辑。

### 2.2 报错: `binance does not have a URL for sapi`
*   **原因**: CCXT 内部尝试检查现货/杠杆接口，但测试网配置未覆盖。
*   **解决**: `src/live_bot.py` 已内置了全量的 URL 映射表，将 `sapi`, `v3` 等所有端点都指向了有效的测试网地址。

### 2.3 无法下单/余额为 0
*   **检查**: 确认 `testnet/config.py` 中的 `REAL_TRADING_ENABLED = True`。
*   **注意**: 在模拟盘模式下，`REAL_TRADING_ENABLED` 意为“允许向测试网发送真实指令”，必须开启才能进行模拟撮合。

## 3. 验证工具
项目提供了一个独立的验证脚本，用于在不启动机器人的情况下测试 API 连通性：

```bash
# 执行全流程测试 (开仓 -> 止损 -> 止盈)
python tests/testnet/test_full_logic.py
```
如果该脚本运行成功，说明您的网络、API Key 和账户状态均正常。