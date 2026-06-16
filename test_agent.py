import os
import shutil
import unittest
import time
from db import init_db, clear_db, DB_FILENAME, get_connection
from basic_search import search_directory_basic
from indexer import index_directory
from searcher import search_index

TEST_DIR = "test_search_workspace"
TEST_DB = "test_search_index.db"

class TestSearchAgent(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Set up a test directory with dummy files
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
        os.makedirs(TEST_DIR)
        
        # Create some folders and text files
        cls.files_info = {
            "file1.txt": "Python is a powerful programming language.\nIt is easy to learn and fun to write code in.",
            "file2.log": "[INFO] Server started successfully.\n[ERROR] Connection failed on database socket.\n[WARNING] Retry attempt 1.",
            "sub/file3.py": "def hello_world():\n    print('Hello World! This is a test file for the search agent.')\n    return True",
            "sub/deep/file4.txt": "Large datasets require specialized database index strategies like inverted index tables.\nSQLite FTS5 works exceptionally well for this task.",
        }
        
        for rel_path, content in cls.files_info.items():
            full_path = os.path.join(TEST_DIR, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
        # Clean test db if exists
        clear_db(TEST_DB)
        init_db(TEST_DB)

    @classmethod
    def tearDownClass(cls):
        # Clean up temporary test files and databases
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
        clear_db(TEST_DB)

    def test_01_basic_search(self):
        """
        Verify that Phase 1 (basic search) works correctly.
        """
        print("\n--- Running Test: Phase 1 Basic Search ---")
        res = search_directory_basic(TEST_DIR, "Connection failed")
        self.assertEqual(len(res['results']), 1)
        self.assertEqual(res['results'][0]['line'], 'Line 2')
        self.assertTrue("file2.log" in res['results'][0]['file'])
        print(f"Basic search found: '{res['results'][0]['content']}' at {res['results'][0]['line']}.")

    def test_02_indexing_and_search_sql(self):
        """
        Verify that Phase 2 (SQL FTS5) indexing and searching matches expectations.
        """
        print("\n--- Running Test: Phase 2 SQLite Indexing ---")
        stats = index_directory(TEST_DIR, db_path=TEST_DB, verbose=False)
        self.assertEqual(stats['new'], 4)
        self.assertEqual(stats['updated'], 0)
        
        # Verify database contents
        conn = get_connection(TEST_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM files;")
        self.assertEqual(cursor.fetchone()[0], 4)
        cursor.execute("SELECT COUNT(*) FROM file_content_fts;")
        self.assertEqual(cursor.fetchone()[0], 10) # Total non-empty lines in mock files
        conn.close()
        
        print("\n--- Running Test: Phase 2 SQLite FTS5 Search ---")
        # Search query with wildcard (inverted -> inverted*)
        res = search_index("inverted index", db_path=TEST_DB)
        self.assertEqual(len(res['results']), 1)
        self.assertTrue("file4.txt" in res['results'][0]['file'])
        self.assertEqual(res['results'][0]['line'], 'Line 1')
        print(f"SQL search found: '{res['results'][0]['content']}' at {res['results'][0]['line']}.")

    def test_03_incremental_indexing(self):
        """
        Verify that incremental indexing correctly identifies changed, new, and deleted files.
        """
        print("\n--- Running Test: Incremental Indexing ---")
        
        # 1. Re-indexing immediately should result in all skipped
        stats = index_directory(TEST_DIR, db_path=TEST_DB, verbose=False)
        self.assertEqual(stats['skipped'], 4)
        self.assertEqual(stats['new'], 0)
        self.assertEqual(stats['updated'], 0)
        print("Verified: Unchanged files correctly skipped.")
        
        # 2. Modify an existing file (change content and modify stat times)
        modified_file = os.path.join(TEST_DIR, "file1.txt")
        # Sleep briefly to ensure stat times would change
        time.sleep(0.1)
        with open(modified_file, 'a', encoding='utf-8') as f:
            f.write("\nAn extra line containing special keywords like Antigravity.")
            
        stats = index_directory(TEST_DIR, db_path=TEST_DB, verbose=False)
        self.assertEqual(stats['updated'], 1)
        self.assertEqual(stats['skipped'], 3)
        self.assertEqual(stats['new'], 0)
        print("Verified: Modified file correctly detected and updated.")
        
        # Check that we can search for the new keyword
        res = search_index("Antigravity", db_path=TEST_DB)
        self.assertEqual(len(res['results']), 1)
        self.assertEqual(res['results'][0]['line'], 'Line 3')
        
        # 3. Add a new file
        new_file = os.path.join(TEST_DIR, "file5.txt")
        with open(new_file, 'w', encoding='utf-8') as f:
            f.write("A completely new file with brand new content.")
            
        stats = index_directory(TEST_DIR, db_path=TEST_DB, verbose=False)
        self.assertEqual(stats['new'], 1)
        self.assertEqual(stats['updated'], 0)
        self.assertEqual(stats['skipped'], 4)
        print("Verified: New file correctly detected and added.")
        
        # 4. Delete a file
        os.remove(new_file)
        stats = index_directory(TEST_DIR, db_path=TEST_DB, verbose=False)
        self.assertEqual(stats['purged'], 1)
        self.assertEqual(stats['skipped'], 4)
        print("Verified: Deleted file correctly detected and purged.")

    def test_04_benchmark_comparison(self):
        """
        Run a microbenchmark to compare search speeds.
        For a small dataset, differences are micro-seconds, but shows the speedup.
        """
        print("\n--- Running Benchmark ---")
        
        # Perform 100 queries in basic search
        start_basic = time.perf_counter()
        for _ in range(100):
            search_directory_basic(TEST_DIR, "socket")
        time_basic = time.perf_counter() - start_basic
        
        # Perform 100 queries in SQL index search
        start_sql = time.perf_counter()
        for _ in range(100):
            search_index("socket", db_path=TEST_DB)
        time_sql = time.perf_counter() - start_sql
        
        print(f"Basic linear scan (100 runs): {time_basic:.4f} seconds")
        print(f"SQL FTS5 index lookup (100 runs): {time_sql:.4f} seconds")
        print(f"Speedup: {time_basic / time_sql:.2f}x")

if __name__ == '__main__':
    unittest.main()
