#!/usr/bin/env python3
"""
Convert MySQL dump to SQLite format
"""

import re
import sys

def convert_mysql_to_sqlite(input_file, output_file):
    """Convert MySQL dump to SQLite compatible format"""
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove MySQL-specific comments and commands
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'-- .*?\n', '\n', content)
    content = re.sub(r'SET .*?;', '', content)
    content = re.sub(r'START TRANSACTION;', '', content)
    content = re.sub(r'COMMIT;', '', content)
    
    # Convert MySQL data types to SQLite equivalents
    # Convert AUTO_INCREMENT
    content = re.sub(r'AUTO_INCREMENT', 'AUTOINCREMENT', content)
    
    # Convert MySQL types to SQLite types
    content = re.sub(r'bigint\(\d+\)', 'INTEGER', content)
    content = re.sub(r'int\(\d+\)', 'INTEGER', content)
    content = re.sub(r'tinyint\(\d+\)', 'INTEGER', content)
    content = re.sub(r'varchar\((\d+)\)', r'VARCHAR(\1)', content)
    content = re.sub(r'datetime\(\d+\)', 'DATETIME', content)
    content = re.sub(r'text', 'TEXT', content)
    content = re.sub(r'longtext', 'TEXT', content)
    content = re.sub(r'decimal\([^)]+\)', 'REAL', content)
    
    # Remove MySQL-specific constraints and engine specifications
    content = re.sub(r'ENGINE=\w+', '', content)
    content = re.sub(r'DEFAULT CHARSET=\w+', '', content)
    content = re.sub(r'COLLATE=[\w_]+', '', content)
    content = re.sub(r'CHECK \([^)]+\)', '', content)
    content = re.sub(r'UNSIGNED', '', content)
    
    # Remove MySQL key definitions that might cause issues
    content = re.sub(r'KEY `[^`]+` \([^)]+\),?', '', content)
    content = re.sub(r'UNIQUE KEY `[^`]+` \([^)]+\),?', '', content)
    
    # Clean up PRIMARY KEY definitions
    content = re.sub(r'PRIMARY KEY \(`(\w+)`\)', r'PRIMARY KEY (\1)', content)
    
    # Remove backticks around column names
    content = re.sub(r'`([^`]+)`', r'\1', content)
    
    # Clean up extra commas and whitespace
    content = re.sub(r',\s*\)', ')', content)
    content = re.sub(r'\n\s*\n', '\n', content)
    
    # Add SQLite-specific settings
    sqlite_content = """
-- SQLite compatible dump
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

""" + content + """

COMMIT;
PRAGMA foreign_keys=ON;
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(sqlite_content)
    
    print(f"Converted {input_file} to {output_file}")

if __name__ == "__main__":
    convert_mysql_to_sqlite("eltanige_eltandb.sql", "eltandb_sqlite.sql")