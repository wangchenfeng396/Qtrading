# 数据库设计文档 (SQLite)

本系统使用 SQLite 3 存储实盘运行数据。数据库文件位于项目根目录下的 `trading_history.db`。

## 1. 连接配置
*   **模式**: WAL (Write-Ahead Logging) 模式开启，支持高并发读写。
*   **线程安全**: `check_same_thread=False`，允许 Flask 多线程访问。

## 2. 表结构设计

### 2.1 权益快照表 (`equity_snapshots`)
用于记录账户资金随时间的变化，绘制资金曲线。

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `timestamp` | TEXT (ISO8601) | **主键**。记录时间，例如 `2024-01-01T12:00:00.123456`。 |
| `total_equity` | REAL | 账户总权益 (余额 + 未实现盈亏)。 |
| `unrealized_pnl`| REAL | 当前持仓的浮动盈亏 (预留字段)。 |

### 2.2 交易操作表 (`trade_operations`)
用于审计机器人的每一次关键动作。

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | INTEGER | **主键** (自增)。 |
| `timestamp` | TEXT | 操作发生时间。 |
| `symbol` | TEXT | 交易对，如 `BTC/USDT`。 |
| `side` | TEXT | 方向：`LONG` (做多) 或 `SHORT` (做空)。 |
| `action` | TEXT | 动作类型：<br>- `ENTRY` (开仓)<br>- `STOP_LOSS_ORDER` (挂止损)<br>- `TP1_ORDER` (挂止盈1)<br>- `ERROR` (报错) |
| `price` | REAL | 挂单价格或成交均价。 |
| `quantity` | REAL | 数量 (BTC)。 |
| `status` | TEXT | 状态：`FILLED` (成交), `NEW` (挂单), `FAILED` (失败)。 |
| `details` | TEXT | 备注信息或错误堆栈。 |

## 3. 数据维护
SQLite 文件会随时间增长。如果文件过大，建议：
1.  停止机器人和 Web 服务。
2.  备份 `.db` 文件。
3.  删除旧文件，重启服务（程序会自动重建空表）。
