import asyncio
import sqlite3
import json
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from logger import db_logger
from config import config

@dataclass
class Task:
    """Represents a task to be executed by the agent."""
    task_id: str
    description: str
    priority: int = 0
    status: str = 'pending'
    created_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create Task from dictionary."""
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Task to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_text(cls, description: str, priority: int = 0) -> 'Task':
        """Create Task from simple text description."""
        return cls(
            task_id=str(uuid.uuid4()),
            description=description,
            priority=priority,
            max_retries=config.MAX_RETRIES
        )
    
    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> 'Task':
        """Create Task from JSON data."""
        task_id = json_data.get('task_id', str(uuid.uuid4()))
        description = json_data.get('description', json_data.get('prompt', ''))
        priority = json_data.get('priority', 0)
        metadata = json_data.get('metadata', {})
        
        return cls(
            task_id=task_id,
            description=description,
            priority=priority,
            max_retries=config.MAX_RETRIES,
            metadata=metadata
        )

class PersistentTaskQueue:
    """Thread-safe asyncio queue with SQLite persistence."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self._queue = asyncio.PriorityQueue()
        self._lock = asyncio.Lock()
        self._task_counter = 0
        self._initialized = False
    
    async def initialize(self):
        """Initialize the queue and load persisted tasks."""
        if self._initialized:
            return
        
        async with self._lock:
            await self._load_persisted_tasks()
            self._initialized = True
            db_logger.log_event('SYSTEM', 'SYSTEM', 'QUEUE_MANAGER', 'INFO', 'Queue initialized')
    
    async def _load_persisted_tasks(self):
        """Load tasks from database on startup."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT task_id, description, priority, status, created_at, retry_count, max_retries
                    FROM tasks 
                    WHERE status IN ('pending', 'running') 
                    ORDER BY priority DESC, created_at ASC
                ''')
                
                loaded_count = 0
                for row in cursor.fetchall():
                    task_id, description, priority, status, created_at, retry_count, max_retries = row
                    task = Task(
                        task_id=task_id,
                        description=description,
                        priority=priority,
                        status='pending',  # Reset running tasks to pending
                        created_at=created_at,
                        retry_count=retry_count,
                        max_retries=max_retries
                    )
                    
                    # Use negative priority for priority queue (higher priority = lower number)
                    await self._queue.put((-priority, self._task_counter, task))
                    self._task_counter += 1
                    loaded_count += 1
                
                db_logger.logger.info(f"Loaded {loaded_count} persisted tasks")
                
        except Exception as e:
            db_logger.logger.error(f"Failed to load persisted tasks: {e}")
    
    async def put(self, task: Task) -> bool:
        """Add a task to the queue."""
        if not self._initialized:
            await self.initialize()
        
        try:
            async with self._lock:
                # Persist to database first
                success = db_logger.log_task_created(task.task_id, task.description, task.priority)
                if not success:
                    return False
                
                # Add to in-memory queue (negative priority for priority queue)
                await self._queue.put((-task.priority, self._task_counter, task))
                self._task_counter += 1
                
                db_logger.log_event(task.task_id, 'SYSTEM', 'QUEUE_MANAGER', 'INFO', 
                                  f'Task queued: {task.description[:50]}...')
                return True
                
        except Exception as e:
            db_logger.logger.error(f"Failed to enqueue task: {e}")
            return False
    
    async def get(self) -> Optional[Task]:
        """Get the next task from the queue."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # This will block until a task is available
            priority, counter, task = await self._queue.get()
            
            db_logger.log_event(task.task_id, 'SYSTEM', 'QUEUE_MANAGER', 'INFO', 
                              f'Task dequeued: {task.description[:50]}...')
            return task
            
        except Exception as e:
            db_logger.logger.error(f"Failed to dequeue task: {e}")
            return None
    
    async def get_nowait(self) -> Optional[Task]:
        """Get the next task from the queue without blocking."""
        if not self._initialized:
            await self.initialize()
        
        try:
            priority, counter, task = self._queue.get_nowait()
            
            db_logger.log_event(task.task_id, 'SYSTEM', 'QUEUE_MANAGER', 'INFO', 
                              f'Task dequeued (nowait): {task.description[:50]}...')
            return task
            
        except asyncio.QueueEmpty:
            return None
        except Exception as e:
            db_logger.logger.error(f"Failed to dequeue task (nowait): {e}")
            return None
    
    async def size(self) -> int:
        """Get the current queue size."""
        if not self._initialized:
            await self.initialize()
        
        return self._queue.qsize()
    
    async def empty(self) -> bool:
        """Check if the queue is empty."""
        if not self._initialized:
            await self.initialize()
        
        return self._queue.empty()
    
    async def add_text_task(self, description: str, priority: int = 0) -> str:
        """Add a task from simple text description."""
        task = Task.from_text(description, priority)
        success = await self.put(task)
        return task.task_id if success else None
    
    async def add_json_task(self, json_data: Dict[str, Any]) -> str:
        """Add a task from JSON data."""
        task = Task.from_json(json_data)
        success = await self.put(task)
        return task.task_id if success else None
    
    async def retry_task(self, task: Task) -> bool:
        """Re-queue a failed task for retry."""
        if task.retry_count >= task.max_retries:
            db_logger.log_event(task.task_id, 'SYSTEM', 'QUEUE_MANAGER', 'WARNING',
                              f'Task exceeded max retries: {task.description[:50]}...')
            return False
        
        # Increment retry count
        task.retry_count += 1
        task.status = 'pending'
        
        # Add back to queue with slightly lower priority
        task.priority = max(0, task.priority - 1)
        
        success = await self.put(task)
        if success:
            db_logger.log_event(task.task_id, 'SYSTEM', 'QUEUE_MANAGER', 'INFO',
                              f'Task queued for retry {task.retry_count}/{task.max_retries}')
        return success
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self._initialized:
            await self.initialize()
        
        queue_size = await self.size()
        task_stats = db_logger.get_task_stats()
        
        return {
            'queue_size': queue_size,
            'total_tasks': sum(task_stats.values()),
            'task_stats': task_stats,
            'initialized': self._initialized
        }
    
    async def pause_queue(self):
        """Pause the queue (for weekly checkpoints)."""
        # This is handled at the worker level, but we can mark it here
        db_logger.log_event('SYSTEM', 'SYSTEM', 'QUEUE_MANAGER', 'INFO', 'Queue paused for checkpoint')
    
    async def resume_queue(self):
        """Resume the queue after checkpoint."""
        db_logger.log_event('SYSTEM', 'SYSTEM', 'QUEUE_MANAGER', 'INFO', 'Queue resumed from checkpoint')
    
    async def clear_completed_tasks(self, days_old: int = 30):
        """Clear old completed tasks from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM tasks 
                    WHERE status = 'completed' 
                    AND completed_at < datetime('now', '-{} days')
                '''.format(days_old))
                
                deleted = cursor.rowcount
                conn.commit()
                
                if deleted > 0:
                    db_logger.log_event('SYSTEM', 'SYSTEM', 'QUEUE_MANAGER', 'INFO',
                                      f'Cleaned up {deleted} old completed tasks')
                return deleted
                
        except Exception as e:
            db_logger.logger.error(f"Failed to clear old tasks: {e}")
            return 0

# Global queue instance
task_queue = PersistentTaskQueue() 