#!/usr/bin/env python3
"""
Extract and import only INSERT statements from converted SQL file
"""

import re
import sqlite3
import sys

def extract_and_import_data(sql_file, db_file):
    """Extract INSERT statements and import data into SQLite database"""
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract all INSERT statements
    insert_statements = re.findall(r'INSERT INTO `?\w+`?.*?;', content, re.DOTALL | re.IGNORECASE)
    
    # Connect to SQLite database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    successful_imports = 0
    failed_imports = 0
    
    # Turn off foreign key constraints during import
    cursor.execute("PRAGMA foreign_keys=OFF;")
    
    for insert in insert_statements:
        try:
            # Clean up the INSERT statement
            # Remove backticks
            insert = re.sub(r'`([^`]+)`', r'\1', insert)
            
            # Fix common issues with quotes in data
            # This is a simple fix - might need more sophisticated handling
            insert = re.sub(r"([^\\])'([^']*)'s", r"\1'\2''s", insert)
            
            print(f"Executing: {insert[:100]}...")
            cursor.execute(insert)
            successful_imports += 1
            
        except Exception as e:
            print(f"Failed to execute INSERT: {str(e)}")
            print(f"Statement: {insert[:200]}...")
            failed_imports += 1
            continue
    
    # Turn foreign key constraints back on
    cursor.execute("PRAGMA foreign_keys=ON;")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print(f"\nImport summary:")
    print(f"Successful imports: {successful_imports}")
    print(f"Failed imports: {failed_imports}")
    
    return successful_imports, failed_imports

if __name__ == "__main__":
    successful, failed = extract_and_import_data("eltandb_sqlite.sql", "db.sqlite3")
    print(f"\nData import completed. Success: {successful}, Failed: {failed}")