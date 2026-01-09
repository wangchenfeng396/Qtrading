import ccxt
import pandas as pd
import clickhouse_connect
from datetime import datetime, timedelta
import time
import sys
import os
import argparse
import logging
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
PROXY_URL = os.getenv("PROXY_URL", "") 

# --- Logging Setup ---
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logger = logging.getLogger("Qtrading_Download")
logger.setLevel(logging.INFO)

file_handler = TimedRotatingFileHandler(
    os.path.join(log_dir, 'download.log'), when='midnight', interval=1, backupCount=30, encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

logger.addHandler(file_handler)
logger.addHandler(console_handler)

def fetch_and_store_daily_data():
    # Parse Arguments
    parser = argparse.ArgumentParser(description="Fetch daily 1s data from Binance API to ClickHouse")
    parser.add_argument('--date', type=str, help='Specific date to download (YYYY-MM-DD), e.g., 2025-01-01')
    args = parser.parse_args()

    logger.info(f"Starting daily data fetch for {SYMBOL_BINANCE}...")

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
        logger.info(">>> Connected to ClickHouse.")
    except Exception as e:
        logger.error(f"❌ ClickHouse Connection Failed: {e}")
        return

    # 2. Determine Fetch Range
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d')
            start_timestamp = int(target_date.timestamp() * 1000)
            # End of that day (23:59:59.999)
            end_date = target_date + timedelta(days=1) - timedelta(milliseconds=1)
            end_timestamp = int(end_date.timestamp() * 1000)
            logger.info(f">>> Mode: Single Date Download ({args.date})")
        except ValueError:
            logger.error("❌ Invalid date format. Use YYYY-MM-DD")
            return
    else:
        # Default: Incremental Fetch
        try:
            result = client.query(f"SELECT max(open_time) FROM {DB_NAME}.{TABLE_NAME}")
            last_time = result.first_item['max(open_time)']
            
            if last_time:
                start_timestamp = int(last_time.timestamp() * 1000) + 1000
                logger.info(f">>> Mode: Incremental Fetch (from {last_time})")
            else:
                yesterday = datetime.now() - timedelta(days=1)
                start_timestamp = int(yesterday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
                logger.info(f">>> Mode: Incremental Fetch (DB empty, from {yesterday})")
                
        except Exception as e:
            logger.warning(f"⚠️ Could not query max time: {e}")
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
        logger.info(f"🌐 Using Proxy: {PROXY_URL}")
        
    exchange = ccxt.binance(exchange_config)
    
    logger.info(f">>> Fetching range: {datetime.fromtimestamp(start_timestamp/1000)} to {datetime.fromtimestamp(end_timestamp/1000)}")

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
                logger.info(f"    Fetched {len(all_ohlcv)} records...")
            
            # If the last fetched candle is already beyond or at end_timestamp, stop
            if ohlcv[-1][0] >= end_timestamp:
                break

        except Exception as e:
            logger.error(f"❌ Error fetching data: {e}")
            break

    if not all_ohlcv:
        logger.info(">>> No data found for this range.")
        return

    logger.info(f">>> Fetched {len(all_ohlcv)} records. Processing...")

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
        logger.info(f"✅ Successfully inserted {len(df_final)} records.")
    except Exception as e:
        logger.error(f"❌ Insert Failed: {e}")

if __name__ == "__main__":
    fetch_and_store_daily_data()