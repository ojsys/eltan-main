#!/usr/bin/env python3
"""
Fixed data import script with proper quote handling
"""

import re
import sqlite3
import sys

def fix_sql_quotes(sql_content):
    """Fix quote escaping issues in SQL content"""
    
    # Split into individual INSERT statements
    insert_statements = re.findall(r'INSERT INTO.*?;', sql_content, re.DOTALL | re.IGNORECASE)
    
    fixed_statements = []
    
    for statement in insert_statements:
        # Remove backticks from table names
        statement = re.sub(r'`([^`]+)`', r'\1', statement)
        
        # Fix apostrophes in quoted values
        # This regex finds VALUES clause and fixes quotes within it
        def fix_values_quotes(match):
            values_content = match.group(1)
            # Replace single quotes within data with doubled single quotes
            # But be careful not to mess up the value separators
            
            # Split by commas that are outside parentheses
            parts = []
            paren_level = 0
            current_part = ""
            
            i = 0
            while i < len(values_content):
                char = values_content[i]
                if char == '(':
                    paren_level += 1
                elif char == ')':
                    paren_level -= 1
                elif char == ',' and paren_level == 0:
                    parts.append(current_part)
                    current_part = ""
                    i += 1
                    continue
                
                current_part += char
                i += 1
            
            if current_part:
                parts.append(current_part)
            
            # Fix quotes in each part
            fixed_parts = []
            for part in parts:
                # Fix quotes in string literals
                part = re.sub(r"'([^']*)'s([^']*)'", r"'\1''s\2'", part)  # Fix possessives
                part = re.sub(r"'([^']*)'([^']*)'", r"'\1''\2'", part)   # Fix general apostrophes
                fixed_parts.append(part)
            
            return "VALUES " + ",".join(fixed_parts)
        
        # Apply the fix to VALUES clauses
        statement = re.sub(r'VALUES\s+(.*)', fix_values_quotes, statement, flags=re.DOTALL)
        
        # Additional specific fixes for common patterns
        statement = re.sub(r"'([^']*)'s ", r"'\1''s ", statement)  # Fix possessive 's
        statement = re.sub(r"'([^']*)'t ", r"'\1''t ", statement)  # Fix contractions like can't
        statement = re.sub(r"'([^']*)'re ", r"'\1''re ", statement) # Fix contractions like they're
        statement = re.sub(r"'([^']*)'ll ", r"'\1''ll ", statement) # Fix contractions like we'll
        statement = re.sub(r"'([^']*)'ve ", r"'\1''ve ", statement) # Fix contractions like I've
        
        fixed_statements.append(statement)
    
    return fixed_statements

def import_data_fixed(sql_file, db_file):
    """Import data with proper quote handling"""
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Get fixed INSERT statements
    insert_statements = fix_sql_quotes(content)
    
    # Connect to SQLite database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    successful_imports = 0
    failed_imports = 0
    failed_details = []
    
    # Turn off foreign key constraints during import
    cursor.execute("PRAGMA foreign_keys=OFF;")
    
    # Process each statement
    for i, insert in enumerate(insert_statements):
        try:
            # Skip statements for tables that don't exist
            if any(table in insert for table in ['membership_old_conference', 'membership_sigcomment', 
                                                'membership_sigmembership', 'membership_sigpost', 
                                                'membership_sigpost_likes', 'membership_sig_leaders']):
                print(f"Skipping statement {i+1}: Table doesn't exist")
                continue
            
            # Skip statements with column issues we know about
            if 'conference_image' in insert or 'abstract_file' in insert:
                print(f"Skipping statement {i+1}: Column doesn't exist")
                continue
            
            # Execute the statement
            print(f"Executing statement {i+1}: {insert[:80]}...")
            cursor.execute(insert)
            successful_imports += 1
            
        except Exception as e:
            error_msg = str(e)
            print(f"Failed statement {i+1}: {error_msg}")
            failed_details.append({
                'statement_num': i+1,
                'error': error_msg,
                'statement': insert[:200]
            })
            failed_imports += 1
            continue
    
    # Turn foreign key constraints back on
    cursor.execute("PRAGMA foreign_keys=ON;")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print(f"\n=== IMPORT SUMMARY ===")
    print(f"Successful imports: {successful_imports}")
    print(f"Failed imports: {failed_imports}")
    
    if failed_details:
        print(f"\n=== FAILED IMPORT DETAILS ===")
        for detail in failed_details[:5]:  # Show first 5 failures
            print(f"Statement {detail['statement_num']}: {detail['error']}")
    
    return successful_imports, failed_imports

if __name__ == "__main__":
    successful, failed = import_data_fixed("eltandb_sqlite.sql", "db.sqlite3")
    print(f"\nFinal result: {successful} successful, {failed} failed")