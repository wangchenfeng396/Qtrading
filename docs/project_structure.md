# 项目结构说明

## 📂 根目录概览

```
Qtrading/
├── src/                # [核心代码] 策略、实盘、回测逻辑
├── scripts/            # [工具脚本] 数据下载、测试连接
├── testnet/            # [模拟环境] 独立的模拟盘配置与启动入口
├── docs/               # [项目文档] 策略说明、配置指南、部署手册
├── logs/               # [运行日志] 自动生成，按天轮转
├── output/             # [回测报告] 存放 HTML 报告文件
├── *.sh                # [快捷脚本] 一键启动实盘、模拟盘、下载器
└── deploy.sh           # [部署脚本] 打包项目用于服务器部署
```

## 🧩 核心模块 (src/)

*   **`live_bot.py`**: 实盘机器人主程序。
    *   **交易执行**: 兼容实盘/模拟盘的下单接口。
    *   **风控引擎**: 内置仓位计算与双重约束。
    *   **订单巡检**: 自动检测 TP1 成交并执行“推保本”操作，防止裸奔。
    *   **消息推送**: 集成 Bark/Telegram 通知。
*   **`backtester.py`**: 回测引擎。复用实盘的资金管理逻辑，对历史数据进行仿真交易。
*   **`strategy_factory.py`**: 策略工厂。用于动态加载不同的交易策略。
*   **`strategies/`**: 策略实现目录。当前核心策略为 `trend_mean_reversion.py`。
*   **`database.py`**: SQLite 数据库管理，用于 Web 监控的数据持久化。
*   **`web_server.py`**: Flask Web 服务，提供可视化看板。

## 🛠 工具脚本 (scripts/)

*   **`day_download_s_to_clickhouse.py`**: 每日增量下载数据（支持指定日期）。
*   **`month_download_s_to_clickhouse.py`**: 按月批量下载历史归档数据。

## 🧪 模拟环境 (testnet/)

*   **`run_simulation.py`**: 模拟盘启动器。它会注入 `testnet/config.py` 配置，并调用 `src` 中的核心逻辑，实现“代码零修改”的仿真运行。

## 🧪 测试套件 (tests/)

*   **`mainnet/test_full_logic.py`**: 实盘环境验证脚本 (消耗真实资金)。
*   **`testnet/test_full_logic.py`**: 模拟盘环境验证脚本。
