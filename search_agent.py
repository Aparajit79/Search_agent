import os
import sys
from database import run_indexer, search_index


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TARGET_FOLDER = "documents"

if __name__ == '__main__':
    # Step 1: Create target folder if it does not exist
    if not os.path.exists(TARGET_FOLDER):
        print(f"Creating local folder '{TARGET_FOLDER}'...")
        os.makedirs(TARGET_FOLDER)
        print("Please place your files inside the 'documents' folder.")
        
    # Step 2: Index all current files inside target folder
    run_indexer(TARGET_FOLDER)
    
    print("\n" + "=" * 50)
    print("Welcome to Search Agent!")
    print("Enter the query and press Enter.")
    print("Type 'exit' to quit.")
    print("=" * 50)
    
    while True:
        user_input = input("\nEnter search term: ").strip()
        if user_input.lower() in ('exit', 'quit'):
            print("Thank You!")
            break
        if not user_input:
            continue
        search_index(user_input)
