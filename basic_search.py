import os
import time
import sys
from document_parser import is_supported_file, extract_text_from_file

def search_directory_basic(directory, query, case_sensitive=False):
    """
    Linearly scans all files in directory for a search query.
    Returns a list of dicts: [{'file': filepath, 'line': line_no/ref, 'content': text}]
    """
    results = []
    total_files_scanned = 0
    total_bytes_scanned = 0
    
    if not case_sensitive:
        query = query.lower()
        
    start_time = time.perf_counter()
    
    for root, dirs, files in os.walk(directory):
        # Skip hidden directories like .git or .venv
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if file.startswith('.'):
                continue
                
            filepath = os.path.join(root, file)
            
            # Simple check: skip if not a supported format
            if not is_supported_file(file):
                continue
                
            total_files_scanned += 1
            try:
                file_size = os.path.getsize(filepath)
                total_bytes_scanned += file_size
                
                content_lines = extract_text_from_file(filepath)
                for line_content, ref in content_lines:
                    match_line = line_content if case_sensitive else line_content.lower()
                    if query in match_line:
                        results.append({
                            'file': filepath,
                            'line': ref,
                            'content': line_content
                        })
            except Exception as e:
                # Silently skip files we cannot read due to permissions or lock issues
                pass
                
    elapsed_time = time.perf_counter() - start_time
    
    return {
        'results': results,
        'scanned_files': total_files_scanned,
        'scanned_bytes': total_bytes_scanned,
        'time_taken_seconds': elapsed_time
    }

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python basic_search.py <directory> <query>")
        sys.exit(1)
        
    dir_to_search = sys.argv[1]
    search_query = sys.argv[2]
    
    print(f"Scanning directory: {dir_to_search} for '{search_query}' (Basic Linear Scan)...")
    res = search_directory_basic(dir_to_search, search_query)
    
    print("\n--- Search Results ---")
    for r in res['results'][:20]: # Limit display to first 20 results
        print(f"{r['file']}:{r['line']} - {r['content']}")
        
    if len(res['results']) > 20:
        print(f"... and {len(res['results']) - 20} more matches.")
        
    print("\n--- Statistics ---")
    print(f"Scanned files: {res['scanned_files']}")
    print(f"Scanned data: {res['scanned_bytes'] / (1024 * 1024):.2f} MB")
    print(f"Total matches found: {len(res['results'])}")
    print(f"Time taken: {res['time_taken_seconds']:.4f} seconds")
