import asyncio
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import traceback

from queue_manager import task_queue, Task
from model_handler import model_handler
from test_runner import test_runner
from git_manager import git_manager
from logger import db_logger
from config import config

class TaskExecutor:
    """Manages worker coroutines that execute tasks from the queue."""
    
    def __init__(self):
        self.workers: Dict[str, asyncio.Task] = {}
        self.worker_states: Dict[str, Dict[str, Any]] = {}
        self.is_paused = False
        self.shutdown_event = asyncio.Event()
    
    async def start_workers(self, worker_count: int = None):
        """Start the specified number of worker coroutines."""
        worker_count = worker_count or config.WORKER_COUNT
        
        db_logger.log_event('SYSTEM', 'SYSTEM', 'TASK_EXECUTOR', 'INFO', 
                          f'Starting {worker_count} workers')
        
        for i in range(worker_count):
            worker_id = f"worker_{i+1}"
            worker_task = asyncio.create_task(self._worker_loop(worker_id))
            self.workers[worker_id] = worker_task
            self.worker_states[worker_id] = {
                'status': 'idle',
                'current_task': None,
                'tasks_completed': 0,
                'tasks_failed': 0,
                'start_time': datetime.now().isoformat()
            }
        
        db_logger.log_event('SYSTEM', 'SYSTEM', 'TASK_EXECUTOR', 'INFO', 
                          f'Started {len(self.workers)} workers')
    
    async def stop_workers(self):
        """Stop all worker coroutines."""
        db_logger.log_event('SYSTEM', 'SYSTEM', 'TASK_EXECUTOR', 'INFO', 
                          'Stopping all workers')
        
        # Signal shutdown
        self.shutdown_event.set()
        
        # Cancel all worker tasks
        for worker_id, worker_task in self.workers.items():
            if not worker_task.done():
                worker_task.cancel()
        
        # Wait for workers to finish
        if self.workers:
            await asyncio.gather(*self.workers.values(), return_exceptions=True)
        
        self.workers.clear()
        self.worker_states.clear()
        
        db_logger.log_event('SYSTEM', 'SYSTEM', 'TASK_EXECUTOR', 'INFO', 
                          'All workers stopped')
    
    async def pause_workers(self):
        """Pause all workers (for weekly checkpoints)."""
        self.is_paused = True
        db_logger.log_event('SYSTEM', 'SYSTEM', 'TASK_EXECUTOR', 'INFO', 
                          'Workers paused for checkpoint')
    
    async def resume_workers(self):
        """Resume workers after checkpoint."""
        self.is_paused = False
        db_logger.log_event('SYSTEM', 'SYSTEM', 'TASK_EXECUTOR', 'INFO', 
                          'Workers resumed from checkpoint')
    
    async def _worker_loop(self, worker_id: str):
        """Main worker loop that processes tasks from the queue."""
        db_logger.log_event('SYSTEM', worker_id, 'TASK_EXECUTOR', 'INFO', 
                          f'Worker {worker_id} started')
        
        try:
            while not self.shutdown_event.is_set():
                # Check if paused
                if self.is_paused:
                    self.worker_states[worker_id]['status'] = 'paused'
                    await asyncio.sleep(1)
                    continue
                
                try:
                    # Update worker state
                    self.worker_states[worker_id]['status'] = 'waiting'
                    
                    # Get next task from queue (with timeout to allow for shutdown)
                    try:
                        task = await asyncio.wait_for(task_queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue  # Check shutdown event again
                    
                    if task is None:
                        continue
                    
                    # Update worker state
                    self.worker_states[worker_id]['status'] = 'working'
                    self.worker_states[worker_id]['current_task'] = task.task_id
                    
                    # Process the task
                    success = await self._process_task(worker_id, task)
                    
                    # Update worker stats
                    if success:
                        self.worker_states[worker_id]['tasks_completed'] += 1
                    else:
                        self.worker_states[worker_id]['tasks_failed'] += 1
                    
                    # Clear current task
                    self.worker_states[worker_id]['current_task'] = None
                    
                except Exception as e:
                    error_msg = f"Worker {worker_id} error: {e}"
                    db_logger.log_event('SYSTEM', worker_id, 'TASK_EXECUTOR', 'ERROR', error_msg)
                    db_logger.logger.error(f"{error_msg}\n{traceback.format_exc()}")
                    
                    # Brief pause before continuing
                    await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            db_logger.log_event('SYSTEM', worker_id, 'TASK_EXECUTOR', 'INFO', 
                              f'Worker {worker_id} cancelled')
            raise
        
        except Exception as e:
            error_msg = f"Worker {worker_id} crashed: {e}"
            db_logger.log_event('SYSTEM', worker_id, 'TASK_EXECUTOR', 'ERROR', error_msg)
            db_logger.logger.error(f"{error_msg}\n{traceback.format_exc()}")
        
        finally:
            self.worker_states[worker_id]['status'] = 'stopped'
            db_logger.log_event('SYSTEM', worker_id, 'TASK_EXECUTOR', 'INFO', 
                              f'Worker {worker_id} stopped')
    
    async def _process_task(self, worker_id: str, task: Task) -> bool:
        """Process a single task through the complete pipeline."""
        try:
            # Log task start
            db_logger.log_task_started(task.task_id, worker_id)
            db_logger.log_event(task.task_id, worker_id, 'TASK_EXECUTOR', 'INFO', 
                              f'Processing task: {task.description[:100]}...')
            
            # Step 1: Generate code using AI model
            db_logger.log_event(task.task_id, worker_id, 'TASK_EXECUTOR', 'INFO', 
                              'Step 1: Generating code with AI model')
            
            generated_code, model_stats = await model_handler.generate_code(
                task.description, task.task_id
            )
            
            if not model_stats.get('success', False) or not generated_code.strip():
                error_msg = f"Code generation failed: {model_stats.get('error', 'No code generated')}"
                await self._handle_task_failure(worker_id, task, error_msg)
                return False
            
            # Step 2: Run tests on generated code
            db_logger.log_event(task.task_id, worker_id, 'TASK_EXECUTOR', 'INFO', 
                              'Step 2: Running tests on generated code')
            
            # First do a quick syntax check
            syntax_valid, syntax_result = await test_runner.quick_syntax_check(
                task.task_id, generated_code
            )
            
            if not syntax_valid:
                error_msg = f"Syntax validation failed: {syntax_result.get('error', 'Invalid syntax')}"
                await self._handle_task_failure(worker_id, task, error_msg)
                return False
            
            # Run full tests
            test_passed, test_result = await test_runner.run_tests(
                task.task_id, generated_code
            )
            
            if not test_passed:
                error_msg = f"Tests failed: {test_result.get('error', 'Unknown test failure')}"
                await self._handle_task_failure(worker_id, task, error_msg)
                return False
            
            # Step 3: Commit and push code changes
            db_logger.log_event(task.task_id, worker_id, 'TASK_EXECUTOR', 'INFO', 
                              'Step 3: Committing code changes')
            
            # Extract code files from generated code
            code_files = test_runner.extract_code_blocks(generated_code)
            
            if code_files:
                # Create commit message
                commit_message = f"Task {task.task_id[:8]}: {task.description[:50]}"
                if len(task.description) > 50:
                    commit_message += "..."
                
                # Write and commit code
                commit_success, commit_hash = git_manager.write_and_commit_code(
                    task.task_id, code_files, commit_message
                )
                
                if not commit_success:
                    db_logger.log_event(task.task_id, worker_id, 'TASK_EXECUTOR', 'WARNING', 
                                      'Git commit failed, but task considered successful')
            
            # Step 4: Log successful completion
            result_summary = {
                'code_files': list(code_files.keys()) if code_files else [],
                'model_stats': model_stats,
                'test_result': test_result,
                'commit_hash': commit_hash if 'commit_hash' in locals() else None
            }
            
            db_logger.log_task_completed(task.task_id, worker_id, str(result_summary))
            db_logger.log_event(task.task_id, worker_id, 'TASK_EXECUTOR', 'INFO', 
                              'Task completed successfully')
            
            return True
            
        except Exception as e:
            error_msg = f"Task processing error: {e}"
            db_logger.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            await self._handle_task_failure(worker_id, task, error_msg)
            return False
    
    async def _handle_task_failure(self, worker_id: str, task: Task, error_message: str):
        """Handle task failure and determine if retry is needed."""
        try:
            # Log the failure
            db_logger.log_task_failed(task.task_id, worker_id, error_message, task.retry_count)
            
            # Check if we should retry
            if task.retry_count < task.max_retries:
                db_logger.log_event(task.task_id, worker_id, 'TASK_EXECUTOR', 'INFO', 
                                  f'Retrying task: attempt {task.retry_count + 1}/{task.max_retries}')
                
                # Re-queue the task for retry
                retry_success = await task_queue.retry_task(task)
                
                if not retry_success:
                    db_logger.log_event(task.task_id, worker_id, 'TASK_EXECUTOR', 'ERROR', 
                                      'Failed to re-queue task for retry')
            else:
                db_logger.log_event(task.task_id, worker_id, 'TASK_EXECUTOR', 'ERROR', 
                                  f'Task failed permanently after {task.max_retries} attempts')
        
        except Exception as e:
            db_logger.logger.error(f"Error handling task failure: {e}")
    
    def get_worker_status(self) -> Dict[str, Any]:
        """Get current status of all workers."""
        return {
            'worker_count': len(self.workers),
            'is_paused': self.is_paused,
            'workers': dict(self.worker_states),
            'total_completed': sum(w.get('tasks_completed', 0) for w in self.worker_states.values()),
            'total_failed': sum(w.get('tasks_failed', 0) for w in self.worker_states.values())
        }
    
    async def add_task_from_text(self, description: str, priority: int = 0) -> Optional[str]:
        """Add a task from text description."""
        return await task_queue.add_text_task(description, priority)
    
    async def add_task_from_json(self, json_data: Dict[str, Any]) -> Optional[str]:
        """Add a task from JSON data."""
        return await task_queue.add_json_task(json_data)
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return await task_queue.get_queue_stats()
    
    async def restart_worker(self, worker_id: str) -> bool:
        """Restart a specific worker."""
        if worker_id not in self.workers:
            return False
        
        try:
            # Cancel old worker
            old_worker = self.workers[worker_id]
            if not old_worker.done():
                old_worker.cancel()
                try:
                    await old_worker
                except asyncio.CancelledError:
                    pass
            
            # Start new worker
            new_worker = asyncio.create_task(self._worker_loop(worker_id))
            self.workers[worker_id] = new_worker
            
            # Reset worker state
            self.worker_states[worker_id] = {
                'status': 'idle',
                'current_task': None,
                'tasks_completed': 0,
                'tasks_failed': 0,
                'start_time': datetime.now().isoformat()
            }
            
            db_logger.log_event('SYSTEM', worker_id, 'TASK_EXECUTOR', 'INFO', 
                              f'Worker {worker_id} restarted')
            return True
            
        except Exception as e:
            db_logger.logger.error(f"Failed to restart worker {worker_id}: {e}")
            return False

# Global task executor instance
task_executor = TaskExecutor() 