import os
import sqlite3
from document_parser import ALL_EXTENSIONS, extract_text_from_file

DATABASE_FILE = "search_index.db"

def init_database():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS file_content_fts;")
    cursor.execute("""
    CREATE VIRTUAL TABLE file_content_fts USING fts5(
        filename UNINDEXED,
        line_no UNINDEXED,
        content,
        tokenize='unicode61'
    );
    """)
    conn.commit()
    conn.close()

def run_indexer(target_folder):
    print(f"\nIndexing files inside '{target_folder}'...")
    init_database()
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Read and index all files in the documents folder
    for root, dirs, files in os.walk(target_folder):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.startswith('.'):
                continue
            _, ext = os.path.splitext(file.lower())
            if ext in ALL_EXTENSIONS:
                filepath = os.path.join(root, file)
                filename = os.path.basename(filepath)
                
                # Extract file text lines and insert them
                content_lines = extract_text_from_file(filepath)
                batch = []
                for line_content, line_no in content_lines:
                    batch.append((filename, line_no, line_content))
                
                if batch:
                    cursor.executemany(
                        "INSERT INTO file_content_fts (filename, line_no, content) VALUES (?, ?, ?);", 
                        batch
                    )
                    
    conn.commit()
    conn.close()
    print("Indexing complete!")

def search_index(query_str):
    query_str = query_str.replace('"', '').strip()
    if not query_str:
        return
        
    words = [w for w in query_str.split() if w]
    if not words:
        return
        
    fts_expression = " AND ".join(f"{word}*" for word in words)
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    sql = """
    SELECT filename, line_no, content
    FROM file_content_fts
    WHERE file_content_fts MATCH ?
    LIMIT 20;
    """
    
    try:
        cursor.execute(sql, (fts_expression,))
        rows = cursor.fetchall()
        
        if not rows:
            print("\nNo matching files found.")
        else:
            print(f"\n--- Found {len(rows)} matches ---")
            for idx, row in enumerate(rows, 1):
                filename, line_no, content = row
                print(f"{idx}. File: {filename} ({line_no})")
                print(f"   [Context] {content}")
                print("-" * 60)
    except sqlite3.OperationalError as e:
        print(f"Search query error: {e}")
    finally:
        conn.close()
