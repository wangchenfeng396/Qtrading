# 服务器部署运维手册

## 1. 自动打包 (本地)

项目内置了智能打包脚本，会自动排除虚拟环境、密钥文件和日志，生成轻量级的压缩包。

```bash
# 在项目根目录执行
./deploy.sh
```
执行成功后，会生成 `Qtrading_deploy_YYYYMMDD_HHMMSS.tar.gz`。

---

## 2. 环境初始化 (服务器)

将压缩包上传到服务器后：

```bash
# 1. 解压
tar -xzvf Qtrading_deploy_xxxx.tar.gz
cd Qtrading

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置密钥 (非常重要！)
cp .env.example .env
vim .env
# -> 填入您的 Binance API Key 和 Proxy 地址
```

---

## 3. 进程管理 (启动/停止)

我们提供了三个快捷脚本，全部支持后台静默运行 (`nohup`)。

| 任务 | 启动命令 | 日志文件 |
| :--- | :--- | :--- |
| **实盘交易** | `./start_live.sh` | `logs/live_bot.log` |
| **模拟盘** | `./start_simulation.sh` | `logs/live_bot.log` |
| **数据同步** | `./start_download.sh` | `logs/download.log` |
| **Web 监控** | `python src/web_server.py` | (控制台输出) |

### 停止进程
脚本启动时会显示 PID。如果忘记了，可以使用：
```bash
# 查找进程
ps -ef | grep python

# 杀掉进程
kill <PID>
```

---

## 4. Web 监控访问

启动 Web 服务后，通过浏览器访问：
`http://服务器IP:5001`

*   **端口**: 5001 (请确保安全组已放行)
*   **功能**: 可实时查看账户权益曲线，并在“实盘”与“模拟盘”数据间切换。
