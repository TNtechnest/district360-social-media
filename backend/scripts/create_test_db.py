"""Create the test database if it doesn't exist."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='district360_user',
    password='district360_pass',
    dbname='postgres'
)
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname='district360_test_db'")
if not cur.fetchone():
    cur.execute('CREATE DATABASE district360_test_db OWNER district360_user')
    print('TEST DB CREATED')
else:
    print('TEST DB EXISTS')
conn.close()
