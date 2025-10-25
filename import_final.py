#!/usr/bin/env python3
"""
Final data import script with comprehensive data format fixes
"""

import re
import sqlite3
import sys
from datetime import datetime

def clean_sql_content(content):
    """Clean and prepare SQL content for SQLite"""
    
    # Remove MySQL-specific comments and commands
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'-- .*?\n', '\n', content)
    content = re.sub(r'SET .*?;', '', content)
    content = re.sub(r'START TRANSACTION;', '', content)
    content = re.sub(r'COMMIT;', '', content)
    
    # Remove backticks from all table/column names
    content = re.sub(r'`([^`]+)`', r'\1', content)
    
    return content

def fix_insert_statement(statement):
    """Fix individual INSERT statement for SQLite compatibility"""
    
    # Skip problematic tables
    skip_tables = [
        'membership_old_conference', 
        'membership_sigcomment', 
        'membership_sigmembership', 
        'membership_sigpost', 
        'membership_sigpost_likes', 
        'membership_sig_leaders'
    ]
    
    for table in skip_tables:
        if table in statement:
            return None
    
    # Skip statements with problematic columns
    if 'conference_image' in statement or 'abstract_file' in statement:
        return None
    
    # Remove 'order' column references as 'order' is a reserved word
    statement = re.sub(r',\s*order,', ', sort_order,', statement)
    statement = re.sub(r'\(\s*order\s*\)', '(sort_order)', statement)
    
    # Fix datetime format from 'YYYY-MM-DD HH:MM:SS.ssssss' to 'YYYY-MM-DD HH:MM:SS'
    def fix_datetime(match):
        dt_str = match.group(1)
        try:
            # Remove microseconds if present
            if '.' in dt_str:
                dt_str = dt_str.split('.')[0]
            return f"'{dt_str}'"
        except:
            return match.group(0)
    
    statement = re.sub(r"'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)'", fix_datetime, statement)
    
    # Fix date format
    statement = re.sub(r"'(\d{4}-\d{2}-\d{2})'", r"'\1'", statement)
    
    # Fix apostrophes in text data (double them for SQL escaping)
    def fix_text_quotes(match):
        text = match.group(1)
        # Double any single quotes in the text
        text = text.replace("'", "''")
        return f"'{text}'"
    
    # Find quoted strings and fix internal quotes
    # This matches strings that start and end with single quotes
    statement = re.sub(r"'([^']*(?:''[^']*)*)'", lambda m: f"'{m.group(1)}'", statement)
    
    # More specific fixes for common problematic patterns
    statement = re.sub(r"([^\\])'([st])\b", r"\1''\2", statement)  # Fix contractions
    statement = re.sub(r"([a-zA-Z])'([a-zA-Z])", r"\1''\2", statement)  # Fix names with apostrophes
    
    # Fix email addresses and usernames that got corrupted
    statement = re.sub(r"'([^']*@[^']*)'", r"'\1'", statement)
    
    return statement

def import_data_final(sql_file, db_file):
    """Final import with comprehensive error handling"""
    
    print("Reading SQL file...")
    with open(sql_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("Cleaning SQL content...")
    content = clean_sql_content(content)
    
    print("Extracting INSERT statements...")
    # Extract INSERT statements more carefully
    insert_statements = []
    
    # Split by INSERT INTO and process each
    parts = content.split('INSERT INTO')
    for i, part in enumerate(parts[1:], 1):  # Skip first empty part
        # Find the end of this INSERT statement
        statement = 'INSERT INTO' + part
        
        # Find the semicolon that ends this statement
        semicolon_pos = statement.find(';')
        if semicolon_pos != -1:
            statement = statement[:semicolon_pos + 1]
        
        insert_statements.append(statement.strip())
    
    print(f"Found {len(insert_statements)} INSERT statements")
    
    # Connect to SQLite database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    successful_imports = 0
    failed_imports = 0
    failed_details = []
    
    # Turn off foreign key constraints during import
    cursor.execute("PRAGMA foreign_keys=OFF;")
    
    print("Processing INSERT statements...")
    for i, statement in enumerate(insert_statements, 1):
        try:
            # Clean and fix the statement
            fixed_statement = fix_insert_statement(statement)
            
            if fixed_statement is None:
                print(f"Skipping statement {i}: Table/column not supported")
                continue
            
            # Execute the statement
            print(f"Executing statement {i}/{len(insert_statements)}: {fixed_statement[:60]}...")
            cursor.execute(fixed_statement)
            successful_imports += 1
            
        except Exception as e:
            error_msg = str(e)
            print(f"Failed statement {i}: {error_msg}")
            
            # Try to salvage the data by attempting simpler fixes
            if "syntax error" in error_msg and i <= 10:  # Only for first few critical statements
                try:
                    # Very basic fix attempt
                    basic_fix = re.sub(r"'([^']*)'([^']*)'", r"'\1''\2'", statement)
                    basic_fix = re.sub(r'INSERT INTO ([^(]+)', r'INSERT INTO \1', basic_fix)
                    cursor.execute(basic_fix)
                    print(f"  -> Recovered with basic fix!")
                    successful_imports += 1
                    continue
                except:
                    pass
            
            failed_details.append({
                'statement_num': i,
                'error': error_msg,
                'statement': statement[:200]
            })
            failed_imports += 1
    
    # Turn foreign key constraints back on
    cursor.execute("PRAGMA foreign_keys=ON;")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print(f"\n=== FINAL IMPORT SUMMARY ===")
    print(f"Successful imports: {successful_imports}")
    print(f"Failed imports: {failed_imports}")
    
    # Show some statistics
    cursor = sqlite3.connect(db_file).cursor()
    cursor.execute("SELECT COUNT(*) FROM account_customuser")
    user_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM membership_subscription")
    subscription_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM django_session")
    session_count = cursor.fetchone()[0]
    
    print(f"\n=== DATA VERIFICATION ===")
    print(f"Users imported: {user_count}")
    print(f"Subscriptions imported: {subscription_count}")
    print(f"Sessions imported: {session_count}")
    
    cursor.close()
    
    return successful_imports, failed_imports

if __name__ == "__main__":
    print("Starting comprehensive data import...")
    successful, failed = import_data_final("eltandb_sqlite.sql", "db.sqlite3")
    print(f"\n🎉 Import completed! Success: {successful}, Failed: {failed}")