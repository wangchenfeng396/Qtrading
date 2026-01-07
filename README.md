# Qtrading 量化交易系统

这是一个基于 Python 和 ClickHouse 的高频量化交易系统，专注于 BTC/USDT 的趋势回踩策略。

## 📁 目录结构

*   `src/`: 核心代码
    *   `main.py`: 回测主程序 (入口)
    *   `backtester.py`: 回测引擎与资金管理
    *   `strategy.py`: 策略逻辑 (EMA 趋势 + 回踩)
    *   `live_bot.py`: 实盘信号生成器 (Live)
    *   `data_loader.py`: 数据加载与聚合
*   `scripts/`: 工具脚本
    *   `month_download_s_to_clickhouse.py`: 下载历史数据 (按月 ZIP)
    *   `day_download_s_to_clickhouse.py`: 下载补全数据 (按日 API)
    *   `fetch_data.py`: 旧版数据下载 (备份)
    *   `test_clickhouse.py`: 数据库连接测试
*   `docs/`: 文档说明
    *   `trading_strategy.md`: **交易策略详细说明书** (推荐阅读)
    *   `README-backtester.md`: 回测系统说明

## 🚀 快速开始

### 1. 环境准备
```bash
# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据准备
确保本地安装并运行 ClickHouse (默认端口 8123)。

```bash
# 方式一：下载历史月份数据 (推荐)
python scripts/month_download_s_to_clickhouse.py --month 2024-01

# 方式二：下载指定日期数据 (补全)
python scripts/day_download_s_to_clickhouse.py --date 2026-01-06
```

### 3. 运行回测
```bash
# 运行指定时间段的回测
python src/main.py --start 2024-01-01 --end 2024-01-07
```
运行后会生成交互式报告 `backtest_report.html`。

### 4. 实盘信号
```bash
python src/live_bot.py
```

## 📊 策略简介
采用 **1H 趋势过滤 + 15m 回踩等待 + 5m 信号触发** 的顺势交易逻辑。
详细说明请参阅 [docs/trading_strategy.md](docs/trading_strategy.md)。