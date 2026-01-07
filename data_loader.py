# data_loader.py
import clickhouse_connect
import pandas as pd
import config

def get_aggregated_data(timeframe_str, start_date, end_date):
    """
    利用 ClickHouse 聚合 1s 数据到指定 timeframe
    timeframe_str: '5m', '15m', '1h'
    """
    
    # 将 timeframe 转换为秒数
    tf_map = {'5m': 300, '15m': 900, '1h': 3600}
    seconds = tf_map.get(timeframe_str)
    
    if not seconds:
        raise ValueError(f"Unsupported timeframe: {timeframe_str}")

    print(f"Loading and aggregating {timeframe_str} data from ClickHouse...")

    query = f"""
    SELECT
        toStartOfInterval(open_time, INTERVAL {seconds} SECOND) as timestamp,
        argMin(open, open_time) as open,
        max(high) as high,
        min(low) as low,
        argMax(close, open_time) as close,
        sum(volume) as volume
    FROM {config.DB_NAME}.{config.SOURCE_TABLE}
    WHERE open_time >= '{start_date}' AND open_time <= '{end_date}'
    GROUP BY timestamp
    ORDER BY timestamp ASC
    """

    client = clickhouse_connect.get_client(
        host=config.CLICKHOUSE_HOST,
        port=config.CLICKHOUSE_PORT,
        username=config.CLICKHOUSE_USER,
        password=config.CLICKHOUSE_PASSWORD
    )
    
    df = client.query_df(query)
    # Ensure timestamp is datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df

def prepare_strategy_data(start_date='2021-01-01', end_date='2021-02-01'):
    """
    拉取 1H, 15m, 5m 数据并对齐到 5m 粒度 (主回测周期)
    """
    # 1. Fetch Data
    df_1h = get_aggregated_data('1h', start_date, end_date)
    df_15m = get_aggregated_data('15m', start_date, end_date)
    df_5m = get_aggregated_data('5m', start_date, end_date)

    print("Merging dataframes...")
    
    # 2. Rename columns for merging
    df_1h.columns = [f"1h_{col}" for col in df_1h.columns]
    df_15m.columns = [f"15m_{col}" for col in df_15m.columns]
    
    # 3. Merge:
    # 我们以 df_5m 为主轴。
    # 对于 10:05 的 5m K线，我们想知道的是：
    # - 1H 趋势：取 10:00 之前最近的一个已完成的 1H 线 (避免未来函数) 
    #   或者取当前的 1H 线 (如果策略允许盘中动态)。
    #   **通常做法**: 比较保守的是取上一根已收盘的大周期。
    #   但在 Pandas 中，我们可以用 reindex + ffill (前向填充)。
    
    # Reset index to make merging easier
    df_5m = df_5m.reset_index()
    df_15m = df_15m.reset_index()
    df_1h = df_1h.reset_index()

    # Merge 5m with 15m (AsOf/Left join with ffill)
    df_merged = pd.merge_asof(
        df_5m, 
        df_15m, 
        on='timestamp', 
        direction='backward' # 获取当前或过去最近的数据
    )
    
    # Merge with 1h
    df_merged = pd.merge_asof(
        df_merged, 
        df_1h, 
        on='timestamp', 
        direction='backward'
    )

    df_merged.set_index('timestamp', inplace=True)
    
    # Clean up NaN (at the very beginning)
    df_merged.dropna(inplace=True)
    
    print(f"Data prepared. Total bars: {len(df_merged)}")
    return df_merged

if __name__ == "__main__":
    # Test
    df = prepare_strategy_data('2024-01-01', '2024-01-05')
    print(df.head())
