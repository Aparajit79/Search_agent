import os
import time
import sys
import sqlite3
from db import get_connection, init_db, DB_FILENAME
from document_parser import is_supported_file, extract_text_from_file

def remove_deleted_files(conn, current_files):
    """
    Remove files from database that no longer exist in the directory.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, filepath FROM files;")
    db_files = cursor.fetchall()
    
    deleted_ids = []
    deleted_paths = []
    
    for file_id, filepath in db_files:
        if filepath not in current_files:
            deleted_ids.append(file_id)
            deleted_paths.append(filepath)
            
    if deleted_ids:
        print(f"Purging {len(deleted_ids)} deleted files from index...")
        # SQLite limits parameters in IN clauses, so we delete in batches or one by one
        # since it's a small lists usually. We can delete in a batch using parameter placeholders.
        for chunk in [deleted_ids[i:i + 500] for i in range(0, len(deleted_ids), 500)]:
            placeholders = ",".join("?" for _ in chunk)
            cursor.execute(f"DELETE FROM file_content_fts WHERE file_id IN ({placeholders});", chunk)
            cursor.execute(f"DELETE FROM files WHERE id IN ({placeholders});", chunk)
        conn.commit()
        
    return deleted_paths

def index_file(conn, filepath, file_id):
    """
    Reads file content and indexes its lines.
    """
    cursor = conn.cursor()
    
    # 1. Clear any existing content for this file (in case we are updating it)
    cursor.execute("DELETE FROM file_content_fts WHERE file_id = ?;", (file_id,))
    
    # 2. Insert lines in batches
    batch = []
    batch_size = 2000
    
    try:
        content_lines = extract_text_from_file(filepath)
        for line_content, ref in content_lines:
            batch.append((file_id, ref, line_content))
            
            if len(batch) >= batch_size:
                cursor.executemany(
                    "INSERT INTO file_content_fts (file_id, line_no, content) VALUES (?, ?, ?);",
                    batch
                )
                batch = []
                
        if batch:
            cursor.executemany(
                "INSERT INTO file_content_fts (file_id, line_no, content) VALUES (?, ?, ?);",
                batch
            )
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        # If we fail to read, remove any partial indices
        cursor.execute("DELETE FROM file_content_fts WHERE file_id = ?;", (file_id,))

def index_directory(directory, db_path=DB_FILENAME, verbose=True):
    """
    Scans a directory and incrementally updates the index database.
    """
    # Ensure database is initialized
    init_db(db_path)
    
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    start_time = time.perf_counter()
    
    files_to_index = []
    current_filepaths = set()
    
    # Walk directory and gather text files
    for root, dirs, files in os.walk(directory):
        # Ignore hidden folders (.git, .venv, etc.)
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.startswith('.'):
                continue
                
            filepath = os.path.abspath(os.path.join(root, file))
            if is_supported_file(file):
                current_filepaths.add(filepath)
                files_to_index.append(filepath)
                
    # 1. Purge deleted files
    deleted_paths = remove_deleted_files(conn, current_filepaths)
    
    # 2. Incrementally index files
    new_files_count = 0
    updated_files_count = 0
    skipped_files_count = 0
    
    # Cache existing files info to minimize db queries during loop
    cursor.execute("SELECT filepath, last_modified, file_size, id FROM files;")
    db_metadata = {row[0]: {'mtime': row[1], 'size': row[2], 'id': row[3]} for row in cursor.fetchall()}
    
    for filepath in files_to_index:
        try:
            stat = os.stat(filepath)
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            # File deleted during indexing
            continue
            
        file_info = db_metadata.get(filepath)
        
        if file_info:
            # Check if file has changed
            if abs(file_info['mtime'] - mtime) < 0.0001 and file_info['size'] == size:
                skipped_files_count += 1
                continue
                
            # File changed: update metadata and index
            updated_files_count += 1
            cursor.execute(
                "UPDATE files SET last_modified = ?, file_size = ? WHERE id = ?;",
                (mtime, size, file_info['id'])
            )
            index_file(conn, filepath, file_info['id'])
        else:
            # New file: insert metadata and index
            new_files_count += 1
            cursor.execute(
                "INSERT INTO files (filepath, last_modified, file_size) VALUES (?, ?, ?);",
                (filepath, mtime, size)
            )
            file_id = cursor.lastrowid
            index_file(conn, filepath, file_id)
            
        # Commit every 100 files to avoid holding locks too long and save memory
        if (new_files_count + updated_files_count) % 100 == 0:
            conn.commit()
            
    conn.commit()
    conn.close()
    
    elapsed_time = time.perf_counter() - start_time
    
    if verbose:
        print(f"\n--- Indexing Completed in {elapsed_time:.4f} seconds ---")
        print(f"New files indexed: {new_files_count}")
        print(f"Updated files: {updated_files_count}")
        print(f"Skipped (unchanged) files: {skipped_files_count}")
        print(f"Purged deleted files: {len(deleted_paths)}")
        
    return {
        'new': new_files_count,
        'updated': updated_files_count,
        'skipped': skipped_files_count,
        'purged': len(deleted_paths),
        'time_seconds': elapsed_time
    }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python indexer.py <directory>")
        sys.exit(1)
        
    dir_to_index = sys.argv[1]
    index_directory(dir_to_index)
