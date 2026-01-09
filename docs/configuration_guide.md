# Qtrading 参数配置说明书

本文档详细解释了 `src/config.py` 及 `testnet/config.py` 中各个参数的作用、取值范围及对策略的影响。

---

## 1. 账户与基础设置 (Account Settings)

| 参数名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `INITIAL_CAPITAL` | `50.0` | **初始本金 (USDT)**<br>仅用于回测和模拟盘初始化。实盘模式下，程序会自动读取交易所真实余额。 |
| `LEVERAGE` | `5` | **杠杆倍数**<br>用于计算最大可持仓数量 (Margin Requirement)。<br>*注意：程序不会自动在交易所调整杠杆倍数，请务必手动在币安 App 中将 BTCUSDT 合约杠杆设为 5x。* |
| `COMMISSION_RATE` | `0.0005` | **手续费率**<br>默认万分之五 (0.05%)，对应币安 Taker 费率。回测扣除手续费依据。 |

---

## 2. 风险管理 (Risk Management)

这是系统中最重要的部分，直接决定账户的生存能力。

| 参数名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `RISK_PER_TRADE_PCT` | `0.02` | **单笔风险百分比 (2%)**<br>每笔交易允许亏损的金额占当前总资金的比例。<br>*公式*: `亏损金额 = 账户余额 * 0.02`。程序会根据此金额反推开仓数量。 |
| `SL_PCT` | `0.015` | **保底止损幅度 (1.5%)**<br>仅当 ATR 动态止损计算失败（如数据不足）时启用的备用硬止损。 |
| `MAX_TRADES_PER_DAY` | `5` | **单日最大交易次数**<br>防止程序在震荡市中过度交易（Over-trading）。达到限制后当日不再开新仓。 |
| `MAX_DAILY_LOSS` | `-2.00` | **单日最大亏损额 (熔断)**<br>当当日累计已实现亏损达到此数值（USDT）时，触发熔断，停止当日交易。建议设为 `初始本金 * 4%`。 |
| `MAX_CONSECUTIVE_LOSS`| `4` | **最大连亏次数 (熔断)**<br>连续亏损 N 笔后，停止当日交易。用于平复情绪和防止策略在极端不适配行情中连续失血。 |

---

## 3. 策略选择 (Strategy Selection)

| 参数名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `ACTIVE_STRATEGY` | `'TrendMeanReversion'` | **当前激活策略**<br>指定 `src/strategies/` 目录下要加载的策略类名称。<br>目前可用: `TrendMeanReversion` |

## 4. 策略参数 (Strategy Parameters)

核心策略：**顺势震荡回归 (Trend Mean Reversion)**

| 参数名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| **止损设置** | | |
| `USE_ATR_FOR_SL` | `True` | **启用 ATR 动态止损**<br>推荐开启。让止损宽度随市场波动率自动呼吸。 |
| `ATR_PERIOD` | `14` | ATR 指标的计算周期。 |
| `ATR_SL_MULTIPLIER`| `2.0` | **ATR 倍数**<br>止损距离 = ATR值 * 2.0。BTC 波动大，2.0 能有效防止被插针扫损。 |
| **趋势过滤** | | |
| `TREND_EMA_PERIOD` | `100` | **趋势判断均线 (1H)**<br>使用 1小时周期的 EMA100 判断大势。价格 > 均线为多头，反之为空头。 |
| **进场信号** | | |
| `RSI_PERIOD` | `14` | RSI 周期 (5分钟级别)。 |
| `RSI_OVERSOLD` | `35` | **超卖阈值**<br>做多条件：RSI < 35。数值越低，接飞刀越安全，但机会越少。 |
| `RSI_OVERBOUGHT` | `65` | **超买阈值**<br>做空条件：RSI > 65。 |
| `BB_PERIOD` | `20` | 布林带周期 (5分钟级别)。 |
| `BB_STD` | `2.0` | 布林带标准差。价格触及 2.0 倍标准差轨道视为极端行情。 |

---

## 4. 止盈策略 (Take Profit)

采用**分批止盈**模式，兼顾胜率和盈亏比。

| 参数名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `TP1_RATIO` | `1.5` | **第一止盈位 (1.5R)**<br>获利金额 = 风险金额 * 1.5 时触发。 |
| `TP1_CLOSE_PCT` | `0.5` | **TP1 平仓比例**<br>触发 TP1 时平掉 50% 仓位，落袋为安。 |
| `MOVE_SL_TO_BE_...`| `True` | **推保本**<br>触发 TP1 后，将剩余仓位的止损价移动到开仓价 (Break Even)。确保这笔交易最终不会亏损。 |
| `TP2_RATIO` | `3.5` | **第二止盈位 (3.5R)**<br>剩余仓位的目标位。用于捕捉大趋势带来的超额收益。 |
| `TP2_CLOSE_PCT` | `1.0` | **TP2 平仓比例**<br>触发 TP2 时平掉剩余所有仓位 (100%)。 |

---

## 5. 实盘与网络 (Live Trading & Network)

| 参数名 | 示例/默认 | 说明 |
| :--- | :--- | :--- |
| `REAL_TRADING_ENABLED`| `False` | **实盘总开关**<br>`True`: 允许真实下单（资金风险！）。<br>`False`: 仅模拟跑，只看行情不交易。 |
| `IS_TESTNET` | `False` | **测试网模式**<br>`True`: 连接 Binance Futures Testnet。<br>`False`: 连接 Binance 实盘主网。 |
| `BINANCE_API_KEY` | `...` | 币安 API Key (建议通过环境变量配置)。 |
| `BINANCE_SECRET` | `...` | 币安 Secret Key。 |
| `PROXY_URL` | `http://...`| **HTTP 代理地址**<br>大陆地区必须配置，例如 `http://127.0.0.1:7890`。 |

---

## 6. 消息推送 (Notifications)

| 参数名 | 说明 |
| :--- | :--- |
| `NOTIFICATION_ENABLED` | 总开关 (`True`/`False`)。 |
| `NOTIFICATION_CHANNELS`| 推送渠道列表，支持 `['bk']` (Bark) 和 `['tg']` (Telegram)。 |
| `BARK_URL` | iPhone Bark App 的推送 URL。 |
| `TELEGRAM_...` | Telegram Bot 的 Token 和 Chat ID。 |
