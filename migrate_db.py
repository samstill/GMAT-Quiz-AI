import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('quiz.db')
cursor = conn.cursor()

print("Starting database migration...")

try:
    # Create a new temporary table with the updated schema
    cursor.execute('''
    CREATE TABLE users_new (
        id INTEGER NOT NULL,
        username VARCHAR NOT NULL,
        email VARCHAR NOT NULL,
        password VARCHAR NOT NULL,
        is_active BOOLEAN,
        created_at DATETIME,
        updated_at DATETIME,
        PRIMARY KEY (id)
    )
    ''')
    
    # Copy data from the old table to the new one, renaming hashed_password to password
    cursor.execute('''
    INSERT INTO users_new (id, username, email, password, is_active, created_at, updated_at)
    SELECT id, username, email, hashed_password, is_active, created_at, updated_at FROM users
    ''')
    
    # Drop the old table
    cursor.execute('DROP TABLE users')
    
    # Rename the new table to the original name
    cursor.execute('ALTER TABLE users_new RENAME TO users')
    
    # Recreate the indices
    cursor.execute('CREATE UNIQUE INDEX ix_users_email ON users (email)')
    cursor.execute('CREATE INDEX ix_users_id ON users (id)')
    cursor.execute('CREATE UNIQUE INDEX ix_users_username ON users (username)')
    
    # Commit the transaction
    conn.commit()
    print("Migration completed successfully!")
    
except Exception as e:
    conn.rollback()
    print(f"Migration failed: {str(e)}")
finally:
    conn.close()
