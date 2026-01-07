使用Python 脚本，使用 ccxt 库从币安（Binance）获取了 BTC/USDT 过去 5 年的日线数据（OHLCV），并将其存储到了 SQLite 数据库中。

  以下是详细的操作步骤和结果：

  1. 环境准备
  我创建了 requirements.txt 文件来管理依赖：
   1 ccxt
   2 pandas
  并为您配置了虚拟环境及安装了相关库。

  2. Python 脚本 (fetch_data.py)
  我编写了脚本 fetch_data.py，主要功能如下：
   * 连接交易所: 使用 ccxt 连接 Binance 公共 API。
   * 获取数据: 自动计算 5 年前的起始时间，并处理分页（Loop）以获取完整数据。默认使用了 1d (日线) 周期，这样数据量适中且速度快（约 1825 条记录）。
   * 存储数据: 使用 pandas 处理数据格式，并保存到本地 SQLite 文件 crypto_data.db 中的 btc_usdt_daily 表。

  3. 执行结果
  脚本已成功运行，输出如下：
   * 数据范围: 2021-01-09 至 2026-01-07
   * 总记录数: 1825 条
   * 数据库文件: crypto_data.db (144K)

  如何查看或再次运行
  您可以在终端中使用以下命令再次运行脚本或查看数据：

   1 # 激活虚拟环境并运行脚本
   2 source venv/bin/activate
   3 python fetch_data.py
   4
   5 # 或者直接使用 sqlite3 查看数据
   6 sqlite3 crypto_data.db "SELECT * FROM btc_usdt_daily ORDER BY timestamp DESC LIMIT 5;"

  注意: 我默认获取的是 日线 (OHLCV) 数据。如果您需要更精细的“交易记录”（如 1分钟 k线 或 逐笔交易 tick data），数据量会非常庞大（分钟线约
  260万条），下载时间会显著增加。如果需要调整周期（例如改为 1h），只需修改脚本中的 timeframe = '1d' 为 timeframe = '1h' 即可。