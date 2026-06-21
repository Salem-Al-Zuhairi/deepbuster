import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deepbuster_history.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create scans table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_url TEXT NOT NULL,
            wordlist_path TEXT,
            threads INTEGER,
            start_time TEXT,
            end_time TEXT,
            status TEXT,
            total_requests INTEGER DEFAULT 0,
            count_200 INTEGER DEFAULT 0,
            count_300 INTEGER DEFAULT 0,
            count_400 INTEGER DEFAULT 0,
            count_500 INTEGER DEFAULT 0
        )
    """)
    
    # Create scan_results table with screenshot_path column
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            path TEXT NOT NULL,
            status_code INTEGER,
            response_size INTEGER,
            timestamp TEXT,
            screenshot_path TEXT,
            FOREIGN KEY (scan_id) REFERENCES scans (id) ON DELETE CASCADE
        )
    """)
    
    # Attempt to alter existing tables for backward compatibility
    try:
        cursor.execute("ALTER TABLE scan_results ADD COLUMN screenshot_path TEXT")
    except sqlite3.OperationalError:
        # Column already exists, safe to ignore
        pass
        
    conn.commit()
    conn.close()

def create_scan(target_url, wordlist_path, threads):
    conn = get_db_connection()
    cursor = conn.cursor()
    start_time = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO scans (target_url, wordlist_path, threads, start_time, status, total_requests)
        VALUES (?, ?, ?, ?, 'running', 0)
    """, (target_url, wordlist_path, threads, start_time))
    scan_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return scan_id

def update_scan_status(scan_id, status, end_time=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if end_time:
        cursor.execute("UPDATE scans SET status = ?, end_time = ? WHERE id = ?", (status, end_time, scan_id))
    else:
        cursor.execute("UPDATE scans SET status = ? WHERE id = ?", (status, scan_id))
    conn.commit()
    conn.close()

def update_scan_stats(scan_id, total_requests, count_200, count_300, count_400, count_500):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE scans 
        SET total_requests = ?, count_200 = ?, count_300 = ?, count_400 = ?, count_500 = ?
        WHERE id = ?
    """, (total_requests, count_200, count_300, count_400, count_500, scan_id))
    conn.commit()
    conn.close()

def add_scan_result(scan_id, path, status_code, response_size):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Avoid duplicate scan results in database
    cursor.execute("SELECT id FROM scan_results WHERE scan_id = ? AND path = ?", (scan_id, path))
    if cursor.fetchone():
        conn.close()
        return
        
    timestamp = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO scan_results (scan_id, path, status_code, response_size, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (scan_id, path, status_code, response_size, timestamp))
    conn.commit()
    conn.close()

def update_screenshot_path(scan_id, path, screenshot_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE scan_results 
        SET screenshot_path = ? 
        WHERE scan_id = ? AND path = ?
    """, (screenshot_path, scan_id, path))
    conn.commit()
    conn.close()

def get_scans_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scans ORDER BY id DESC")
    rows = cursor.fetchall()
    scans = [dict(row) for row in rows]
    conn.close()
    return scans

def get_scan_results(scan_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scan_results WHERE scan_id = ? ORDER BY id ASC", (scan_id,))
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results

# Automatically initialize database
init_db()
