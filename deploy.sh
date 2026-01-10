#!/bin/bash

# ==========================================
# Qtrading 部署打包脚本
# ==========================================

# 1. 设置包名 (带时间戳)
APP_NAME="Qtrading"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
PACKAGE_NAME="${APP_NAME}_deploy_${TIMESTAMP}.tar.gz"

# 2. 定义排除列表 (Exclude List)
# 排除虚拟环境、日志、本地缓存、Git信息、历史数据库等
EXCLUDE_PARAMS=(
    "--exclude=.git"
    "--exclude=.gitignore"
    #"--exclude=.env"           # 关键：不打包本地密钥！服务器上需重新配置
    "--exclude=.env.example"
    "--exclude=__pycache__"
    "--exclude=*.pyc"
    "--exclude=venv"           # 不打包依赖库，服务器上重新 install
    "--exclude=logs/*"         # 不打包本地日志
    "--exclude=output/*"
    "--exclude=temp_download"
    "--exclude=*.db"           # 不打包本地 SQLite 数据库
    "--exclude=.DS_Store"
    "--exclude=.idea"
    "--exclude=.vscode"
    "--exclude=backtest_report.html"
)

echo "📦 开始打包 Qtrading 系统..."
echo "📄 目标文件: $PACKAGE_NAME"

# 3. 执行打包
# 使用 tar 命令将当前目录打包，同时应用排除规则
tar -czvf "$PACKAGE_NAME" "${EXCLUDE_PARAMS[@]}" .

echo "------------------------------------------"
if [ -f "$PACKAGE_NAME" ]; then
    echo "✅ 打包成功！"
    echo "大小: $(du -h "$PACKAGE_NAME" | cut -f1)"
    echo ""
    echo "🚀 部署指南:"
    echo "1. 将 $PACKAGE_NAME 上传到服务器"
    echo "   scp $PACKAGE_NAME user@server_ip:/path/to/deploy/"
    echo "2. 解压:"
    echo "   tar -xzvf $PACKAGE_NAME"
    echo "3. 环境初始化:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    echo "4. 配置密钥:"
    echo "   cp .env.example .env"
    echo "   vim .env  # 填入您的 API Key"
    echo "5. 启动服务:"
    echo "   ./start_live.sh"
else
    echo "❌ 打包失败！"
    exit 1
fi
