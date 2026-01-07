from sqlalchemy import text
from database import engine

def migrate():
    with engine.connect() as conn:
        try:
            # Check if column exists is hard in raw sqlite without PRAGMA
            # Just try adding it, catch error if exists
            conn.execute(text("ALTER TABLE newsletters ADD COLUMN status VARCHAR(50) DEFAULT 'unread'"))
            conn.commit()
            print("Migration successful: Added status column.")
        except Exception as e:
            if "duplicate column name" in str(e):
                print("Column 'status' already exists.")
            else:
                print(f"Migration failed or not needed: {e}")

if __name__ == "__main__":
    migrate()
