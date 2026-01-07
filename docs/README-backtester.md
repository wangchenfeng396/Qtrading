  文件结构说明

   * config.py: 策略与风控配置。
   * data_loader.py: 高效的 ClickHouse 数据聚合引擎。
   * strategy.py: 策略逻辑（1H趋势 + 15m回踩 + 5m触发）。
   * backtester.py: 核心回测逻辑与资金管理。
   * main.py: 主程序，生成交互式中文报告。
   * download_to_clickhouse.py: 数据下载与入库工具（支持按月）。
   * test_clickhouse.py: 数据库连接测试工具。

   1. `config.py`:
       * 定义了您严格的风控规则：$50 本金, $0.50 (1%) 单笔风险, 5x 杠杆。
       * 定义了止盈策略：1R 减半推保本，2R 出清。
       * 定义了日内限制：日亏 -$1.50 停手, 连亏 3 单停手。

   2. `data_loader.py`:
       * 核心亮点: 它不在 Python 中处理庞大的 1s 数据。而是直接发送 SQL 指令给 ClickHouse，让数据库瞬间聚合出 1H, 15m, 5m 的 K 线数据。
       * 然后使用 pd.merge_asof 将多周期数据对齐到 5m 的时间轴上，确保回测无未来函数。

   3. `strategy.py`:
       * 1H: Close > EMA(50) 判多。
       * 15m: Close < EMA(20) 判回踩。
       * 5m: Close 上穿 EMA(20) 触发进场。
       * 已经移除了 pandas_ta 依赖，改用原生 Pandas 实现，轻量且快。

   4. `backtester.py`:
       * 这是回测引擎的核心，包含一个状态机。
       * 它严格模拟了您的资金曲线、每日重置计数器、连亏计数器。
       * 实现了复杂的订单管理：部分平仓 (Partial Close) 和 止损移动 (Move SL to BE)。

   5. `main.py`:
       * 程序的入口，负责调度以上模块并输出结果和图表。