import ccxt
import pandas as pd
import clickhouse_connect
from datetime import datetime, timedelta
import time
import sys
import argparse

# --- Configuration ---
SYMBOL_BINANCE = 'BTC/USDT'
TABLE_NAME = 'btc_usdt_1s'
DB_NAME = 'crypto_data'

# ClickHouse Configuration
CLICKHOUSE_HOST = '192.168.66.10'
CLICKHOUSE_PORT = 18123
CLICKHOUSE_USER = 'default'
CLICKHOUSE_PASSWORD = 'uming'

# Proxy Configuration (Optional)
# e.g., "http://127.0.0.1:7890"
PROXY_URL = "" 

def fetch_and_store_daily_data():
    # Parse Arguments
    parser = argparse.ArgumentParser(description="Fetch daily 1s data from Binance API to ClickHouse")
    parser.add_argument('--date', type=str, help='Specific date to download (YYYY-MM-DD), e.g., 2025-01-01')
    args = parser.parse_args()

    print(f"[{datetime.now()}] Starting daily data fetch for {SYMBOL_BINANCE}...")

    # 1. Setup ClickHouse
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST, 
            port=CLICKHOUSE_PORT, 
            username=CLICKHOUSE_USER, 
            password=CLICKHOUSE_PASSWORD
        )
        # Verify DB and Table
        client.command(f'CREATE DATABASE IF NOT EXISTS {DB_NAME}')
        print(">>> Connected to ClickHouse.")
    except Exception as e:
        print(f"❌ ClickHouse Connection Failed: {e}")
        return

    # 2. Determine Fetch Range
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d')
            start_timestamp = int(target_date.timestamp() * 1000)
            # End of that day (23:59:59.999)
            end_date = target_date + timedelta(days=1) - timedelta(milliseconds=1)
            end_timestamp = int(end_date.timestamp() * 1000)
            print(f">>> Mode: Single Date Download ({args.date})")
        except ValueError:
            print("❌ Invalid date format. Use YYYY-MM-DD")
            return
    else:
        # Default: Incremental Fetch
        try:
            result = client.query(f"SELECT max(open_time) FROM {DB_NAME}.{TABLE_NAME}")
            last_time = result.first_item['max(open_time)']
            
            if last_time:
                start_timestamp = int(last_time.timestamp() * 1000) + 1000
                print(f">>> Mode: Incremental Fetch (from {last_time})")
            else:
                yesterday = datetime.now() - timedelta(days=1)
                start_timestamp = int(yesterday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
                print(f">>> Mode: Incremental Fetch (DB empty, from {yesterday})")
                
        except Exception as e:
            print(f"⚠️ Could not query max time: {e}")
            yesterday = datetime.now() - timedelta(days=1)
            start_timestamp = int(yesterday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        
        end_timestamp = int(datetime.now().timestamp() * 1000)

    # 3. Setup Exchange
    exchange_config = {
        'enableRateLimit': True,
    }
    if PROXY_URL:
        exchange_config['proxies'] = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
        print(f"🌐 Using Proxy: {PROXY_URL}")
        
    exchange = ccxt.binance(exchange_config)
    
    print(f">>> Fetching range: {datetime.fromtimestamp(start_timestamp/1000)} to {datetime.fromtimestamp(end_timestamp/1000)}")

    # 4. Loop Fetch (Pagination)
    limit = 1000
    all_ohlcv = []
    current_since = start_timestamp
    
    while current_since < end_timestamp:
        try:
            # We want to fetch up to end_timestamp
            ohlcv = exchange.fetch_ohlcv(SYMBOL_BINANCE, '1s', since=current_since, limit=limit)
            
            if not ohlcv:
                break
            
            # Filter out any data beyond end_timestamp (if api returns more)
            valid_ohlcv = [x for x in ohlcv if x[0] <= end_timestamp]
            
            if not valid_ohlcv:
                break
                
            all_ohlcv.extend(valid_ohlcv)
            
            # Next batch
            current_since = ohlcv[-1][0] + 1000
            
            # Progress
            if len(all_ohlcv) % 50000 == 0:
                print(f"    Fetched {len(all_ohlcv)} records...")
            
            # If the last fetched candle is already beyond or at end_timestamp, stop
            if ohlcv[-1][0] >= end_timestamp:
                break

        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            break

    if not all_ohlcv:
        print(">>> No data found for this range.")
        return

    print(f">>> Fetched {len(all_ohlcv)} records. Processing...")

    # 5. Process & Insert
    columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    df = pd.DataFrame(all_ohlcv, columns=columns)
    
    df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close_time'] = df['open_time'] + timedelta(seconds=1) - timedelta(milliseconds=1)
    
    # Fill missing columns required by schema
    df['quote_volume'] = 0.0
    df['trades'] = 0
    df['taker_buy_base'] = 0.0
    df['taker_buy_quote'] = 0.0
    
    # Reorder to match DB Schema
    df_final = df[[
        'open_time', 'open', 'high', 'low', 'close', 'volume', 
        'close_time', 'quote_volume', 'trades', 
        'taker_buy_base', 'taker_buy_quote'
    ]]
    
    # 6. Insert
    try:
        client.insert_df(f'{DB_NAME}.{TABLE_NAME}', df_final)
        print(f"✅ Successfully inserted {len(df_final)} records.")
    except Exception as e:
        print(f"❌ Insert Failed: {e}")

if __name__ == "__main__":
    fetch_and_store_daily_data()