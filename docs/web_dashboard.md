# Web 监控面板使用指南

本项目提供了一个基于 Flask 和 SQLite 的轻量级 Web 监控系统，用于实时查看机器人的**账户权益曲线**和**交易操作日志**。

## 1. 架构说明

*   **数据隔离**: 系统支持多环境监控，实盘与模拟盘数据完全分离。
    *   **实盘数据库**: `trading_history_live.db`
    *   **模拟盘数据库**: `trading_history_testnet.db`
*   **后端**: `src/web_server.py` (Flask)
    *   提供 API 接口并支持 `?env=live|testnet` 参数切换数据源。
*   **前端**: `src/templates/dashboard.html`
    *   支持一键切换监控环境。
    *   每 5 秒自动刷新数据。

## 2. 启动监控

在激活虚拟环境后，运行：

```bash
python src/web_server.py
```

服务启动后，在浏览器访问：
> **http://localhost:5001**

---

## 3. 功能模块

### 3.1 环境切换 (Environment Switch)
页面右上角提供下拉菜单，可在 **🔴 实盘 (Live)** 和 **🟢 模拟盘 (Testnet)** 之间即时切换。切换后，资金曲线和操作记录会同步更新为对应环境的数据。

### 3.2 账户权益曲线 (Equity Curve)
*   实时展示账户总资产 (USDT) 的变动趋势。
*   自动平滑绘制，支持缩放和悬停查看。

### 3.3 最近操作 (Recent Operations)
以表格形式展示最近的操作日志，包括开仓 (ENTRY)、挂单 (ORDER)、报错 (ERROR) 等关键审计信息。

---

## 4. 远程访问 (可选)

默认情况下，Web 服务监听 `0.0.0.0:5001`。
*   如果您在云服务器上运行，请确保安全组/防火墙已开放 **5001** 端口。
*   访问地址为 `http://您的服务器IP:5001`。
