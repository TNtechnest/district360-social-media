"""One-time fix: add missing updated_at columns to audit_log and activity_log."""
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app('development')
with app.app_context():
    fixes = [
        ('audit_log',    'updated_at'),
        ('activity_log', 'updated_at'),
    ]
    for table, col in fixes:
        try:
            db.session.execute(text(
                f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} TIMESTAMP WITH TIME ZONE'
            ))
            db.session.execute(text(
                f'UPDATE {table} SET {col} = created_at WHERE {col} IS NULL'
            ))
            db.session.commit()
            print(f'  {table}.{col}: OK')
        except Exception as e:
            db.session.rollback()
            print(f'  {table}.{col}: {e}')

    # Check all columns on audit_log
    result = db.session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name='audit_log' ORDER BY ordinal_position")
    )
    print('audit_log columns:', [r[0] for r in result])
