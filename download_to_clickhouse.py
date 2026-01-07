import requests
import zipfile
import io
import pandas as pd
import clickhouse_connect
from datetime import datetime, timedelta
import os
import shutil

# --- Configuration ---
SYMBOL = 'BTCUSDT'
TIMEFRAME = '1s'
START_DATE = datetime(2021, 1, 1) # Start from Jan 2021
END_DATE = datetime.now()
TEMP_DIR = 'temp_download'

# ClickHouse Configuration
CLICKHOUSE_HOST = 'localhost'
CLICKHOUSE_PORT = 8123
CLICKHOUSE_USER = 'default'
CLICKHOUSE_PASSWORD = '' # Leave empty if no password
DB_NAME = 'crypto_data'
TABLE_NAME = 'btc_usdt_1s'

def get_month_list(start, end):
    current = start
    while current <= end:
        yield current
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

def download_and_ingest():
    # 1. Setup ClickHouse
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST, 
            port=CLICKHOUSE_PORT, 
            username=CLICKHOUSE_USER, 
            password=CLICKHOUSE_PASSWORD
        )
        
        # Create Database if not exists
        client.command(f'CREATE DATABASE IF NOT EXISTS {DB_NAME}')
        
        # Create Table
        # Binance Kline Format:
        # Open time, Open, High, Low, Close, Volume, Close time, Quote asset volume, Number of trades, Taker buy base asset volume, Taker buy quote asset volume, Ignore
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
        print("ClickHouse table checked/created.")
        
    except Exception as e:
        print(f"Failed to connect to ClickHouse: {e}")
        print("Please ensure ClickHouse is running and credentials are correct.")
        return

    # 2. Setup Temp Dir
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    # 3. Iterate Months
    for date in get_month_list(START_DATE, END_DATE):
        year_str = date.strftime('%Y')
        month_str = date.strftime('%m')
        
        # Skip current month (files usually not available until month ends)
        if date.year == END_DATE.year and date.month == END_DATE.month:
            print(f"Skipping current month {year_str}-{month_str} (incomplete).")
            continue

        file_name = f"{SYMBOL}-{TIMEFRAME}-{year_str}-{month_str}.zip"
        url = f"https://data.binance.vision/data/spot/monthly/klines/{SYMBOL}/{TIMEFRAME}/{file_name}"
        
        print(f"Processing {year_str}-{month_str}...")
        
        try:
            # Download
            response = requests.get(url)
            if response.status_code == 404:
                print(f"  File not found: {url}")
                continue
            response.raise_for_status()
            
            # Extract
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                # The zip usually contains one csv file
                csv_filename = z.namelist()[0]
                z.extract(csv_filename, TEMP_DIR)
                csv_path = os.path.join(TEMP_DIR, csv_filename)
                
                # Read CSV
                # No header in Binance files
                columns = [
                    'open_time', 'open', 'high', 'low', 'close', 'volume', 
                    'close_time', 'quote_volume', 'trades', 
                    'taker_buy_base', 'taker_buy_quote', 'ignore'
                ]
                
                df = pd.read_csv(csv_path, names=columns)
                
                # Drop 'ignore' column
                df.drop(columns=['ignore'], inplace=True)
                
                # Prepare for Insert
                # Ensure types match ClickHouse schema
                # ClickHouse DateTime64 expects milliseconds if defined as (3)
                # Binance timestamps are already in ms
                
                # Insert
                client.insert_df(f'{DB_NAME}.{TABLE_NAME}', df)
                print(f"  Ingested {len(df)} records.")
                
                # Cleanup
                os.remove(csv_path)

        except Exception as e:
            print(f"  Error processing {year_str}-{month_str}: {e}")

    # Cleanup Temp Dir
    shutil.rmtree(TEMP_DIR)
    print("Done!")

if __name__ == "__main__":
    download_and_ingest()
