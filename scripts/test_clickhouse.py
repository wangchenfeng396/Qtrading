import clickhouse_connect

# --- Configuration (Must match download_to_clickhouse.py) ---
CLICKHOUSE_HOST = '192.168.66.10'
CLICKHOUSE_PORT = 18123
CLICKHOUSE_USER = 'default'
CLICKHOUSE_PASSWORD = 'uming' # Leave empty if no password
DB_NAME = 'crypto_data'

def test_connection():
    print(f"Connecting to ClickHouse at {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}...")
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST, 
            port=CLICKHOUSE_PORT, 
            username=CLICKHOUSE_USER, 
            password=CLICKHOUSE_PASSWORD
        )
        
        # 1. Check version
        version = client.command('SELECT version()')
        print(f"✅ Connection successful!")
        print(f"✅ ClickHouse version: {version}")
        
        # 2. Check databases
        databases = client.command('SHOW DATABASES')
        print(f"✅ Available databases: {databases}")
        
        # 3. Check if our database exists
        db_exists = client.command(f"SELECT count() FROM system.databases WHERE name = '{DB_NAME}'")
        if db_exists:
            print(f"✅ Database '{DB_NAME}' already exists.")
            tables = client.command(f"SHOW TABLES FROM {DB_NAME}")
            print(f"✅ Tables in '{DB_NAME}': {tables}")
        else:
            print(f"ℹ️ Database '{DB_NAME}' does not exist yet (it will be created by the download script).")

        client.close()
        
    except Exception as e:
        print(f"❌ Connection failed!")
        print(f"Error details: {e}")
        print("\nPossible issues:")
        print("1. ClickHouse server is not running.")
        print("2. Port 8123 (HTTP) is blocked or incorrect.")
        print("3. Credentials (user/password) are incorrect.")
        print(f"4. If using Docker, ensure -p 8123:8123 is mapped.")

if __name__ == "__main__":
    test_connection()
