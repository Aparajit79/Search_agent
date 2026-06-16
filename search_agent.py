import argparse
import os
import sys

# Ensure stdout uses UTF-8 to prevent encoding crashes on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from db import get_connection, DB_FILENAME
from indexer import index_directory
from searcher import search_index

def show_status(db_path=DB_FILENAME):
    """
    Retrieves and displays statistics about the index database.
    """
    if not os.path.exists(db_path):
        print(f"Index database '{db_path}' does not exist. Please run the 'index' command first.")
        return
        
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM files;")
        total_files = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM file_content_fts;")
        total_lines = cursor.fetchone()[0]
        
        db_size_bytes = os.path.getsize(db_path)
        db_size_mb = db_size_bytes / (1024 * 1024)
        
        print("\n--- Search Agent Index Status ---")
        print(f"Database File: {os.path.abspath(db_path)}")
        print(f"Database Size: {db_size_mb:.2f} MB")
        print(f"Total Files Indexed: {total_files}")
        print(f"Total Text Lines Indexed: {total_lines}")
    except Exception as e:
        print(f"Error reading index status: {e}")
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(
        description="Python File Search Agent - Efficiently searches folders using SQLite FTS5."
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Index parser
    index_parser = subparsers.add_parser("index", help="Index or update a directory")
    index_parser.add_argument(
        "--dir", 
        default=".", 
        help="Directory to index (default: current directory)"
    )
    
    # Search parser
    search_parser = subparsers.add_parser("search", help="Search the index")
    search_parser.add_argument(
        "query", 
        help="Search terms or phrases"
    )
    search_parser.add_argument(
        "--limit", 
        type=int, 
        default=20, 
        help="Maximum number of results to display (default: 20)"
    )
    search_parser.add_argument(
        "--phrase", 
        action="store_true", 
        help="Search for the exact phrase rather than independent words"
    )
    
    # Status parser
    subparsers.add_parser("status", help="Show statistics of the search index")
    
    args = parser.parse_args()
    
    if args.command == "index":
        target_dir = os.path.abspath(args.dir)
        if not os.path.isdir(target_dir):
            print(f"Error: Directory '{target_dir}' does not exist.")
            sys.exit(1)
        print(f"Indexing directory: {target_dir}")
        index_directory(target_dir)
        
    elif args.command == "search":
        print(f"Searching index for: '{args.query}' (Phrase mode: {args.phrase})")
        res = search_index(args.query, limit=args.limit, phrase_search=args.phrase)
        
        results = res['results']
        if not results:
            print("No matching files found.")
        else:
            print(f"\n--- Found {len(results)} matches (Search time: {res['time_seconds'] * 1000:.2f} ms) ---")
            for idx, r in enumerate(results, 1):
                # Print relative path or basename for clean output
                file_rel = os.path.relpath(r['file']) if os.path.isabs(r['file']) else r['file']
                print(f"{idx}. {file_rel}:{r['line']}")
                print(f"   [Content] {r['content']}")
                print("-" * 50)
                
    elif args.command == "status":
        show_status()
        
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
