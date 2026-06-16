import sqlite3
import time
import sys
from db import get_connection, DB_FILENAME

def format_fts_query(query_str, phrase_search=False):
    """
    Format a query string to be safe and compatible with SQLite FTS5.
    If phrase_search is True, wraps the query in double quotes.
    Otherwise, cleans it and allows default FTS5 behavior.
    """
    # Clean up double quotes and strip whitespace
    query_str = query_str.replace('"', '').strip()
    
    if not query_str:
        return ""
        
    if phrase_search:
        # Exact phrase query: "hello world"
        return f'"{query_str}"'
    else:
        # Keyword query: split by space, search for all words (AND)
        # We also allow wildcards on each word (e.g., hello -> hello*)
        words = [w for w in query_str.split() if w]
        if not words:
            return ""
        # Combine words with AND and append wildcard * to each word for partial matching
        fts_terms = [f"{word}*" for word in words]
        return " AND ".join(fts_terms)

def search_index(query, db_path=DB_FILENAME, limit=50, phrase_search=False):
    """
    Queries the FTS5 virtual table for matches.
    Returns ranked search results with files, line numbers, and matched line contents.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    fts_query = format_fts_query(query, phrase_search)
    if not fts_query:
        return {'results': [], 'time_seconds': 0.0, 'query': fts_query}
        
    start_time = time.perf_counter()
    
    # SQLite BM25 returns a lower score (more negative) for more relevant documents.
    # We sort ascending by bm25(file_content_fts) so best matches come first.
    sql = """
    SELECT 
        f.filepath,
        fts.line_no,
        fts.content,
        bm25(file_content_fts) as rank
    FROM file_content_fts fts
    JOIN files f ON f.id = fts.file_id
    WHERE file_content_fts MATCH ?
    ORDER BY rank ASC
    LIMIT ?;
    """
    
    try:
        cursor.execute(sql, (fts_query, limit))
        rows = cursor.fetchall()
        results = [
            {
                'file': row[0],
                'line': row[1],
                'content': row[2],
                'rank': row[3]
            }
            for row in rows
        ]
    except sqlite3.OperationalError as e:
        print(f"SQL search error (Query: '{fts_query}'): {e}")
        results = []
        
    elapsed_time = time.perf_counter() - start_time
    conn.close()
    
    return {
        'results': results,
        'time_seconds': elapsed_time,
        'query_used': fts_query
    }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python searcher.py <query> [--phrase]")
        sys.exit(1)
        
    query_text = sys.argv[1]
    is_phrase = "--phrase" in sys.argv
    
    print(f"Searching index for: '{query_text}' (Phrase mode: {is_phrase})...")
    res = search_index(query_text, phrase_search=is_phrase)
    
    print("\n--- Search Results ---")
    for idx, r in enumerate(res['results'], 1):
        print(f"{idx}. {r['file']}:{r['line']} [Rank: {r['rank']:.4f}]")
        print(f"   {r['content']}")
        print()
        
    print("--- Statistics ---")
    print(f"Total matches returned: {len(res['results'])}")
    print(f"Search time: {res['time_seconds'] * 1000:.2f} ms")
    print(f"FTS Query compiled: {res['query_used']}")
