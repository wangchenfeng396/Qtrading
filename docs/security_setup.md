# 安全配置指南

为了保护您的 API 密钥和隐私信息，本系统采用了 **Environment Variables (环境变量)** 的方式来管理敏感配置。

我们使用 `.env` 文件来本地存储这些变量。该文件已被加入 `.gitignore`，因此**不会**被提交到版本控制系统中。

## 1. 初始设置

### 1.1 创建 .env 文件
在项目根目录下，复制示例文件：
```bash
cp .env.example .env
```

### 1.2 填写配置
使用文本编辑器打开 `.env` 文件，并填入您的真实信息：

```ini
# --- 币安实盘 (Mainnet) ---
# 申请地址: https://www.binance.com/en/my/settings/api-management
BINANCE_API_KEY="您的实盘API Key"
BINANCE_SECRET="您的实盘Secret Key"

# --- 币安模拟盘 (Testnet) ---
# 申请地址: https://testnet.binancefuture.com/
TESTNET_API_KEY="您的测试网API Key"
TESTNET_SECRET="您的测试网Secret Key"

# --- 消息推送 (可选) ---
# Bark (iPhone): https://api.day.app/您的Key/
BARK_URL="https://api.day.app/xxxx/"

# Telegram
TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
TELEGRAM_CHAT_ID="123456789"

# --- 网络代理 (可选) ---
# 如果在国内，通常需要配置。例如 Clash 默认端口:
PROXY_URL="http://127.0.0.1:7890"
```

---

## 2. 验证配置

配置完成后，您可以运行实盘脚本进行连接测试：

```bash
# 启动实盘机器人 (它会自动读取 .env)
./start_live.sh
```

如果配置正确，您将在日志中看到：
> `🌐 使用代理: http://127.0.0.1:7890` (如果配置了代理)
> `💰 账户可用余额: $xxxx.xx` (如果 API Key 正确)

---

## 3. 安全提示

*   **绝对不要** 将包含真实 Key 的 `.env` 文件发送给他人或上传到 GitHub。
*   **API 权限**: 为实盘 API Key 开启 **"Enable Futures" (允许合约)** 权限，但 **务必关闭 "Enable Withdrawals" (允许提现)**。
*   **服务器安全**: 确保运行机器人的服务器安全，定期更新密码。
