import requests
import zipfile
import io
import pandas as pd
import clickhouse_connect
from datetime import datetime, timedelta
import os
import shutil
import sys
import argparse

# --- Configuration ---
SYMBOL = 'BTCUSDT'
TIMEFRAME = '1s'
START_DATE = datetime(2025, 1, 1) # Start from Jan 2025
END_DATE = datetime.now()
TEMP_DIR = 'temp_download'

# ClickHouse Configuration
CLICKHOUSE_HOST = '192.168.66.10'
CLICKHOUSE_PORT = 18123
CLICKHOUSE_USER = 'default'
CLICKHOUSE_PASSWORD = 'uming' # Leave empty if no password
DB_NAME = 'crypto_data'
TABLE_NAME = 'btc_usdt_1s'

def get_month_list(start, end):
    months = []
    current = start
    while current <= end:
        # Skip current month (incomplete)
        if not (current.year == end.year and current.month == end.month):
            months.append(current)
        
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return months

def download_file(url, desc):
    response = requests.get(url, stream=True)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024 * 1024  # 1MB
    data = io.BytesIO()
    downloaded = 0
    
    print(f"  [Download] {desc}: ", end='', flush=True)
    for chunk in response.iter_content(chunk_size=block_size):
        data.write(chunk)
        downloaded += len(chunk)
        if total_size > 0:
            percent = (downloaded / total_size) * 100
            print(f"\r  [Download] {desc}: {percent:.1f}% ({downloaded/(1024*1024):.1f}MB)", end='', flush=True)
    print("\n", end='')
    return data

def download_and_ingest():
    # Parse Arguments
    parser = argparse.ArgumentParser(description="Download Binance 1s data to ClickHouse")
    parser.add_argument('--month', type=str, help='Specific month to download (YYYY-MM), e.g., 2023-01')
    args = parser.parse_args()

    # Determine Date Range
    if args.month:
        try:
            target_date = datetime.strptime(args.month, '%Y-%m')
            # For a single month
            all_months = [target_date]
            print(f">>> Task Started: Single Month Mode: {args.month}")
        except ValueError:
            print("❌ Invalid date format. Use YYYY-MM")
            return
    else:
        all_months = get_month_list(START_DATE, END_DATE)
        print(f">>> Task Started: Downloading {TIMEFRAME} data for {len(all_months)} months.")

    # 1. Setup ClickHouse
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST, 
            port=CLICKHOUSE_PORT, 
            username=CLICKHOUSE_USER, 
            password=CLICKHOUSE_PASSWORD
        )
        
        client.command(f'CREATE DATABASE IF NOT EXISTS {DB_NAME}')
        
        create_table_query = f'''
        CREATE TABLE IF NOT EXISTS {DB_NAME}.{TABLE_NAME} (
            open_time DateTime64(3),
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume Float64,
            close_time DateTime64(3),
            quote_volume Float64,
            trades UInt64,
            taker_buy_base Float64,
            taker_buy_quote Float64
        ) ENGINE = MergeTree()
        ORDER BY open_time
        '''
        client.command(create_table_query)
        print(">>> ClickHouse connection established and table verified.")
        
    except Exception as e:
        print(f"❌ Failed to connect to ClickHouse: {e}")
        return

    # 2. Setup Temp Dir
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    
    total_months = len(all_months)
    total_records_all = 0

    print("-" * 60)

    # 3. Iterate Months
    for idx, date in enumerate(all_months):
        year_str = date.strftime('%Y')
        month_str = date.strftime('%m')
        month_label = f"{year_str}-{month_str}"
        
        overall_progress = ((idx + 1) / total_months) * 100
        print(f"[{overall_progress:.1f}%] Processing Month {idx+1}/{total_months}: {month_label}")

        file_name = f"{SYMBOL}-{TIMEFRAME}-{year_str}-{month_str}.zip"
        url = f"https://data.binance.vision/data/spot/monthly/klines/{SYMBOL}/{TIMEFRAME}/{file_name}"
        
        try:
            # Download with progress
            file_data = download_file(url, file_name)
            if not file_data:
                print(f"  ⚠️  File not found (skipping): {file_name}")
                continue
            
            # Extract
            with zipfile.ZipFile(file_data) as z:
                csv_filename = z.namelist()[0]
                z.extract(csv_filename, TEMP_DIR)
                csv_path = os.path.join(TEMP_DIR, csv_filename)
                
                # Read CSV
                columns = [
                    'open_time', 'open', 'high', 'low', 'close', 'volume', 
                    'close_time', 'quote_volume', 'trades', 
                    'taker_buy_base', 'taker_buy_quote', 'ignore'
                ]
                
                print(f"  [Ingest] Reading {csv_filename}...", end='', flush=True)
                df = pd.read_csv(csv_path, names=columns)
                df.drop(columns=['ignore'], inplace=True)
                
                # Fix: Check for microsecond timestamps (16 digits) vs millisecond (13 digits)
                # Year 2262 (Pandas max) is approx 9.2e12 ms.
                # If values are larger than 1e14, they are likely microseconds.
                if not df.empty and df['open_time'].max() > 100000000000000: # > 1e14
                    print(" (Detected microsecond timestamps, adjusting...)", end='')
                    df['open_time'] = df['open_time'] // 1000
                    df['close_time'] = df['close_time'] // 1000

                df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
                df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
                print(f" Done ({len(df)} rows).")
                
                # Insert
                print(f"  [Ingest] Writing to ClickHouse...", end='', flush=True)
                client.insert_df(f'{DB_NAME}.{TABLE_NAME}', df)
                total_records_all += len(df)
                print(f" Done. Total records in DB: {total_records_all:,}")
                
                # Cleanup
                os.remove(csv_path)

        except Exception as e:
            print(f"\n  ❌ Error processing {month_label}: {e}")

        print("-" * 30)

    # Cleanup Temp Dir
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    
    print(f"\n✅ Task Completed! Total records ingested: {total_records_all:,}")

if __name__ == "__main__":
    download_and_ingest()
