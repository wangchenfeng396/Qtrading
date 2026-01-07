import ccxt
import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta

def fetch_and_store_data():
    # 1. Setup Exchange (Binance)
    # enableRateLimit: True handles the sleeping automatically to respect exchange limits
    exchange = ccxt.binance({
        'enableRateLimit': True, 
    })

    symbol = 'BTC/USDT'
    timeframe = '1m'  # 1 minute data
    limit = 1000      # Max items per request for Binance
    
    # 2. Calculate Start Time (5 years ago)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)
    since = int(start_date.timestamp() * 1000)

    print(f"Fetching {symbol} {timeframe} data starting from {start_date}...")
    print("This may take a while (approx. 20-40 minutes) due to rate limits and data size.")

    # Database setup
    db_file = 'crypto_data.db'
    table_name = 'btc_usdt_1m'
    conn = sqlite3.connect(db_file)
    
    batch_data = []
    total_records = 0
    first_batch = True
    
    columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

    start_time_perf = time.time()

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            
            if len(ohlcv) == 0:
                print("No more data received.")
                break
            
            batch_data.extend(ohlcv)
            
            # Update 'since' for next iteration
            last_timestamp = ohlcv[-1][0]
            since = last_timestamp + 1
            
            # Progress update
            if len(batch_data) % 10000 < limit: # approximate check to print occasionally
                current_time_str = datetime.fromtimestamp(last_timestamp / 1000).strftime('%Y-%m-%d %H:%M')
                print(f"Fetched up to {current_time_str} | Buffered: {len(batch_data)} | Total Saved: {total_records}")

            # Checkpoint: Write to DB every 50,000 records
            if len(batch_data) >= 50000:
                df = pd.DataFrame(batch_data, columns=columns)
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                if first_batch:
                    df.to_sql(table_name, conn, if_exists='replace', index=False)
                    first_batch = False
                else:
                    df.to_sql(table_name, conn, if_exists='append', index=False)
                
                total_records += len(df)
                print(f">> Checkpoint: Saved {len(df)} records. Total in DB: {total_records}")
                batch_data = [] # Clear memory

            # Break if reached current time
            if last_timestamp >= int(end_date.timestamp() * 1000):
                print("Reached end date.")
                break

        except Exception as e:
            print(f"Error fetching data: {e}")
            # Try to save what we have before exiting?
            break

    # 3. Save any remaining data
    if batch_data:
        df = pd.DataFrame(batch_data, columns=columns)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        if first_batch:
            df.to_sql(table_name, conn, if_exists='replace', index=False)
        else:
            df.to_sql(table_name, conn, if_exists='append', index=False)
        total_records += len(df)
        print(f">> Final Save: {len(df)} records.")

    conn.close()
    
    elapsed = time.time() - start_time_perf
    print(f"\nDone! Saved {total_records} records to '{table_name}' in '{db_file}'.")
    print(f"Total time elapsed: {elapsed/60:.2f} minutes.")

if __name__ == "__main__":
    fetch_and_store_data()
