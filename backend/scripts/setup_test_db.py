"""Grant CREATEDB to district360_user, then create district360_test_db."""
import psycopg2

# Connect as district360_user to district360_db (which they own)
try:
    conn = psycopg2.connect(
        host='localhost', dbname='district360_db',
        user='district360_user', password='district360_pass'
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Check if test DB exists
    cur.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        ('district360_test_db',)
    )
    if cur.fetchone():
        print('district360_test_db: already exists')
    else:
        # Try to create it directly
        cur.execute('CREATE DATABASE district360_test_db')
        print('district360_test_db: CREATED')
    conn.close()
except psycopg2.errors.InsufficientPrivilege:
    print('Need CREATEDB privilege. Run as superuser:')
    print('  psql -U postgres -c "ALTER USER district360_user CREATEDB;"')
    print('  psql -U postgres -c "CREATE DATABASE district360_test_db OWNER district360_user;"')
except Exception as e:
    print('Error:', e)
