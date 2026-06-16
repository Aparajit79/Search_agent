import sqlite3
import os

DB_FILENAME = "search_index.db"

def get_connection(db_path=DB_FILENAME):
    """
    Returns a SQLite connection. Enables foreign keys.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    # Set busy_timeout to avoid lock contention
    conn.execute("PRAGMA busy_timeout = 5000;")
    # Optimize write speed (WAL mode)
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db(db_path=DB_FILENAME):
    """
    Initializes the database schema if it doesn't exist.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # Metadata table for files
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filepath TEXT UNIQUE,
        last_modified REAL,
        file_size INTEGER
    );
    """)
    
    # FTS5 Virtual Table for full-text indexing of file lines
    # We store the file_id and line_no as UNINDEXED since they are metadata, 
    # not text to tokenize and index.
    try:
        cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS file_content_fts USING fts5(
            file_id UNINDEXED,
            line_no UNINDEXED,
            content,
            tokenize='unicode61'
        );
        """)
    except sqlite3.OperationalError as e:
        # Check if FTS5 is supported by the SQLite version
        if "no such module: fts5" in str(e).lower():
            # Fallback to FTS4 if FTS5 is not available (though standard Python 3.x builds usually have FTS5)
            print("Warning: FTS5 not supported. Falling back to FTS4 virtual table.")
            cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS file_content_fts USING fts4(
                file_id,
                line_no,
                content,
                tokenize=unicode61
            );
            """)
        else:
            raise e
            
    conn.commit()
    conn.close()

def clear_db(db_path=DB_FILENAME):
    """
    Clears all tables (used for testing/resetting).
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS file_content_fts;")
    cursor.execute("DROP TABLE IF EXISTS files;")
    conn.commit()
    conn.close()
    
    # Clean up WAL files if they exist
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass
        try:
            os.remove(db_path + "-shm")
        except OSError:
            pass
        try:
            os.remove(db_path + "-wal")
        except OSError:
            pass
