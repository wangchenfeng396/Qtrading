# 数据下载脚本说明

`scripts/` 目录下包含用于从币安获取历史数据的工具脚本。

## 1. 历史数据下载 (按月)
`month_download_s_to_clickhouse.py`

从 Binance Vision 下载官方归档的 **ZIP 压缩包**，解压并导入 ClickHouse。这是获取大量历史数据最快、最稳定的方式。

*   **用法**:
    ```bash
    # 下载指定月份
    python scripts/month_download_s_to_clickhouse.py --month 2024-01
    
    # 默认模式 (下载代码中配置的所有月份)
    python scripts/month_download_s_to_clickhouse.py
    ```

## 2. 实时数据补全 (按日)
`day_download_s_to_clickhouse.py`

通过币安 API (CCXT) 获取最近的 1秒 K线数据。适用于补充最近几天（Binance Vision 尚未归档）的数据，或每日定时运行保持数据库最新。

*   **用法**:
    ```bash
    # 下载指定日期 (00:00 - 23:59)
    python scripts/day_download_s_to_clickhouse.py --date 2026-01-06
    
    # 增量模式 (自动从数据库最后一条记录开始下载到当前时间)
    python scripts/day_download_s_to_clickhouse.py
    ```

*   **后台运行**:
    使用根目录下的 `start_download.sh` 可以将其作为后台进程启动，日志记录在 `logs/download.log`。

## 3. 数据库连接测试
`test_clickhouse.py`

用于验证本地 Python 环境是否能成功连接到 ClickHouse 数据库。

*   **用法**:
    ```bash
    python scripts/test_clickhouse.py
    ```
