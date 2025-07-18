import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import config

class DatabaseLogger:
    """Handles all database operations for logging tasks, results, and system events."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self.ensure_db_directory()
        self.init_database()
        
        # Setup file logging as well
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('agent.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def ensure_db_directory(self):
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def init_database(self):
        """Initialize the SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tasks table - for task queue persistence
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    worker_id TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    result TEXT,
                    error_message TEXT
                )
            ''')
            
            # Execution logs table - for detailed logging
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    task_id TEXT,
                    worker_id TEXT,
                    log_level TEXT,
                    component TEXT,
                    message TEXT,
                    details TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                )
            ''')
            
            # Git commits table - for tracking code changes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS git_commits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    commit_hash TEXT,
                    commit_message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    files_changed TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                )
            ''')
            
            # Model stats table - for tracking AI model performance
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    model_type TEXT,
                    model_name TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    response_time REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                )
            ''')
            
            # System state table - for crash recovery
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_state (
                    id INTEGER PRIMARY KEY,
                    last_checkpoint TIMESTAMP,
                    uptime_start TIMESTAMP,
                    worker_states TEXT,
                    queue_state TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            # Logger will be available after this method completes
            print("Database initialized successfully")
    
    def log_task_created(self, task_id: str, description: str, priority: int = 0) -> bool:
        """Log a new task creation."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO tasks 
                    (task_id, description, priority, status, created_at)
                    VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                ''', (task_id, description, priority))
                conn.commit()
                self.log_event(task_id, 'SYSTEM', 'SYSTEM', 'INFO', f'Task created: {description[:100]}...')
                return True
        except Exception as e:
            self.logger.error(f"Failed to log task creation: {e}")
            return False
    
    def log_task_started(self, task_id: str, worker_id: str) -> bool:
        """Log when a task is started by a worker."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE tasks 
                    SET status = 'running', worker_id = ?, started_at = CURRENT_TIMESTAMP
                    WHERE task_id = ?
                ''', (worker_id, task_id))
                conn.commit()
                self.log_event(task_id, worker_id, 'TASK_EXECUTOR', 'TASK_STARTED', f'Task started by worker {worker_id}')
                return True
        except Exception as e:
            self.logger.error(f"Failed to log task start: {e}")
            return False
    
    def log_task_completed(self, task_id: str, worker_id: str, result: str = None) -> bool:
        """Log when a task is completed successfully."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE tasks 
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP, result = ?
                    WHERE task_id = ?
                ''', (result, task_id))
                conn.commit()
                self.log_event(task_id, worker_id, 'TASK_EXECUTOR', 'TASK_COMPLETED', f'Task completed successfully')
                return True
        except Exception as e:
            self.logger.error(f"Failed to log task completion: {e}")
            return False
    
    def log_task_failed(self, task_id: str, worker_id: str, error_message: str, retry_count: int) -> bool:
        """Log when a task fails."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE tasks 
                    SET status = 'failed', error_message = ?, retry_count = ?
                    WHERE task_id = ?
                ''', (error_message, retry_count, task_id))
                conn.commit()
                self.log_event(task_id, worker_id, 'TASK_EXECUTOR', 'TASK_FAILED', f'Task failed: {error_message}')
                return True
        except Exception as e:
            self.logger.error(f"Failed to log task failure: {e}")
            return False
    
    def log_event(self, task_id: str, worker_id: str, component: str, level: str, message: str, details: Dict[str, Any] = None) -> bool:
        """Log a general event."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                details_json = json.dumps(details) if details else None
                cursor.execute('''
                    INSERT INTO execution_logs 
                    (task_id, worker_id, log_level, component, message, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (task_id, worker_id, level, component, message, details_json))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to log event: {e}")
            return False
    
    def log_git_commit(self, task_id: str, commit_hash: str, commit_message: str, files_changed: List[str]) -> bool:
        """Log a git commit."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO git_commits 
                    (task_id, commit_hash, commit_message, files_changed)
                    VALUES (?, ?, ?, ?)
                ''', (task_id, commit_hash, commit_message, json.dumps(files_changed)))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to log git commit: {e}")
            return False
    
    def log_model_stats(self, task_id: str, model_type: str, model_name: str, 
                       prompt_tokens: int, completion_tokens: int, response_time: float) -> bool:
        """Log AI model usage statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO model_stats 
                    (task_id, model_type, model_name, prompt_tokens, completion_tokens, response_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (task_id, model_type, model_name, prompt_tokens, completion_tokens, response_time))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to log model stats: {e}")
            return False
    
    def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent execution logs."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM execution_logs 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
                
                columns = [description[0] for description in cursor.description]
                logs = []
                for row in cursor.fetchall():
                    log_dict = dict(zip(columns, row))
                    if log_dict['details']:
                        log_dict['details'] = json.loads(log_dict['details'])
                    logs.append(log_dict)
                return logs
        except Exception as e:
            self.logger.error(f"Failed to get recent logs: {e}")
            return []
    
    def get_task_stats(self) -> Dict[str, int]:
        """Get task statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT status, COUNT(*) as count 
                    FROM tasks 
                    GROUP BY status
                ''')
                stats = dict(cursor.fetchall())
                return {
                    'pending': stats.get('pending', 0),
                    'running': stats.get('running', 0),
                    'completed': stats.get('completed', 0),
                    'failed': stats.get('failed', 0)
                }
        except Exception as e:
            self.logger.error(f"Failed to get task stats: {e}")
            return {'pending': 0, 'running': 0, 'completed': 0, 'failed': 0}
    
    def save_system_state(self, worker_states: Dict[str, Any], queue_state: Dict[str, Any]) -> bool:
        """Save current system state for crash recovery."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO system_state 
                    (id, worker_states, queue_state, updated_at)
                    VALUES (1, ?, ?, CURRENT_TIMESTAMP)
                ''', (json.dumps(worker_states), json.dumps(queue_state)))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to save system state: {e}")
            return False
    
    def load_system_state(self) -> Optional[Dict[str, Any]]:
        """Load system state for crash recovery."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT worker_states, queue_state FROM system_state WHERE id = 1')
                row = cursor.fetchone()
                if row:
                    return {
                        'worker_states': json.loads(row[0]) if row[0] else {},
                        'queue_state': json.loads(row[1]) if row[1] else {}
                    }
                return None
        except Exception as e:
            self.logger.error(f"Failed to load system state: {e}")
            return None
    
    def cleanup_old_logs(self, max_entries: int = None) -> bool:
        """Clean up old log entries to prevent database bloat."""
        max_entries = max_entries or config.MAX_LOG_ENTRIES
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM execution_logs 
                    WHERE id NOT IN (
                        SELECT id FROM execution_logs 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    )
                ''', (max_entries,))
                deleted = cursor.rowcount
                conn.commit()
                if deleted > 0:
                    self.logger.info(f"Cleaned up {deleted} old log entries")
                return True
        except Exception as e:
            self.logger.error(f"Failed to cleanup old logs: {e}")
            return False

# Global logger instance
db_logger = DatabaseLogger() 