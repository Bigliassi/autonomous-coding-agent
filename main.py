#!/usr/bin/env python3
"""
Autonomous Coding Agent - Main Entry Point

This is the main application that coordinates all components of the autonomous coding agent:
- Task queue management
- Worker coroutines
- Flask web server
- File watching for tasks.yaml
- Weekly checkpoints
- Crash recovery
"""

import asyncio
import json
import signal
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import config
from logger import db_logger
from queue_manager import task_queue
from task_executor import task_executor
from weekly_summary import summary_generator
from server.app import start_flask_server, agent_state

class TaskFileHandler(FileSystemEventHandler):
    """Handler for watching tasks.yaml file changes."""
    
    def __init__(self, main_app):
        self.main_app = main_app
        self.last_modified = 0
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if event.src_path.endswith('tasks.yaml'):
            # Debounce rapid file changes
            current_time = time.time()
            if current_time - self.last_modified < 2:
                return
            
            self.last_modified = current_time
            
            try:
                asyncio.run_coroutine_threadsafe(
                    self.main_app.load_tasks_from_file('tasks.yaml'),
                    self.main_app.loop
                )
                db_logger.logger.info("Detected tasks.yaml changes, reloading tasks")
            except Exception as e:
                db_logger.logger.error(f"Error loading tasks from file: {e}")

class AutonomousAgent:
    """Main autonomous coding agent application."""
    
    def __init__(self):
        self.loop = None
        self.shutdown_event = asyncio.Event()
        self.flask_thread = None
        self.file_observer = None
        self.state_save_task = None
        self.checkpoint_task = None
        self.uptime_start = datetime.now()
        self.last_checkpoint = None
        self.is_running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        db_logger.logger.info(f"Received signal {signum}, initiating shutdown...")
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.shutdown_event.set)
        else:
            sys.exit(0)
    
    async def initialize(self):
        """Initialize all components."""
        try:
            db_logger.logger.info("Initializing Autonomous Coding Agent...")
            
            # Initialize queue
            await task_queue.initialize()
            
            # Load previous state if exists
            await self._load_system_state()
            
            # Update agent state
            agent_state['is_running'] = True
            agent_state['uptime_start'] = self.uptime_start.isoformat()
            
            # Calculate next checkpoint
            if self.last_checkpoint:
                next_checkpoint = self.last_checkpoint + timedelta(days=config.CHECKPOINT_DAYS)
            else:
                next_checkpoint = self.uptime_start + timedelta(days=config.CHECKPOINT_DAYS)
            
            agent_state['checkpoint_due'] = next_checkpoint.isoformat()
            
            self.is_running = True
            db_logger.logger.info("Agent initialization completed")
            
        except Exception as e:
            db_logger.logger.error(f"Failed to initialize agent: {e}")
            raise
    
    async def start(self):
        """Start the autonomous agent."""
        try:
            # Initialize components
            await self.initialize()
            
            # Start Flask server in separate thread
            self._start_flask_server()
            
            # Start file watcher
            self._start_file_watcher()
            
            # Start workers
            await task_executor.start_workers()
            
            # Start background tasks
            self._start_background_tasks()
            
            # Load initial tasks if tasks.yaml exists
            if Path('tasks.yaml').exists():
                await self.load_tasks_from_file('tasks.yaml')
            
            db_logger.logger.info("🚀 Autonomous Coding Agent started successfully!")
            db_logger.logger.info(f"   Dashboard: http://{config.FLASK_HOST}:{config.FLASK_PORT}")
            db_logger.logger.info(f"   Workers: {config.WORKER_COUNT}")
            db_logger.logger.info(f"   Model: {config.MODEL_TYPE}")
            
            # Main event loop
            await self._main_loop()
            
        except Exception as e:
            db_logger.logger.error(f"Error starting agent: {e}")
            raise
        finally:
            await self._shutdown()
    
    async def _main_loop(self):
        """Main event loop - wait for shutdown signal."""
        try:
            while not self.shutdown_event.is_set():
                # Check for weekly checkpoint
                if self._should_run_checkpoint():
                    await self._run_weekly_checkpoint()
                
                # Brief pause to avoid busy waiting
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            db_logger.logger.info("Main loop cancelled")
        except Exception as e:
            db_logger.logger.error(f"Error in main loop: {e}")
    
    def _start_flask_server(self):
        """Start Flask server in a separate thread."""
        def run_server():
            try:
                start_flask_server()
            except Exception as e:
                db_logger.logger.error(f"Flask server error: {e}")
        
        self.flask_thread = threading.Thread(target=run_server, daemon=True)
        self.flask_thread.start()
        db_logger.logger.info(f"Flask server started on {config.FLASK_HOST}:{config.FLASK_PORT}")
    
    def _start_file_watcher(self):
        """Start file system watcher for tasks.yaml."""
        try:
            self.file_observer = Observer()
            handler = TaskFileHandler(self)
            self.file_observer.schedule(handler, '.', recursive=False)
            self.file_observer.start()
            db_logger.logger.info("File watcher started for tasks.yaml")
        except Exception as e:
            db_logger.logger.error(f"Failed to start file watcher: {e}")
    
    def _start_background_tasks(self):
        """Start background maintenance tasks."""
        # State saving task
        self.state_save_task = asyncio.create_task(self._state_save_loop())
        
        # Log cleanup task
        cleanup_task = asyncio.create_task(self._log_cleanup_loop())
        
        db_logger.logger.info("Background tasks started")
    
    async def _state_save_loop(self):
        """Periodically save system state for crash recovery."""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(config.STATE_SAVE_INTERVAL)
                await self._save_system_state()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            db_logger.logger.error(f"Error in state save loop: {e}")
    
    async def _log_cleanup_loop(self):
        """Periodically clean up old logs."""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(3600)  # Every hour
                db_logger.cleanup_old_logs()
                await task_queue.clear_completed_tasks()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            db_logger.logger.error(f"Error in log cleanup loop: {e}")
    
    async def load_tasks_from_file(self, filename: str):
        """Load tasks from YAML or JSON file."""
        try:
            file_path = Path(filename)
            if not file_path.exists():
                db_logger.logger.warning(f"Tasks file not found: {filename}")
                return
            
            content = file_path.read_text()
            
            # Try JSON first, then YAML
            try:
                import json
                data = json.loads(content)
            except json.JSONDecodeError:
                try:
                    import yaml
                    data = yaml.safe_load(content)
                except ImportError:
                    db_logger.logger.error("PyYAML not installed, cannot parse YAML files")
                    return
                except Exception as e:
                    db_logger.logger.error(f"Error parsing YAML: {e}")
                    return
            
            # Process tasks
            if isinstance(data, list):
                tasks = data
            elif isinstance(data, dict) and 'tasks' in data:
                tasks = data['tasks']
            else:
                db_logger.logger.error("Invalid file format in tasks file")
                return
            
            # Add tasks to queue
            loaded_count = 0
            for task_data in tasks:
                try:
                    if isinstance(task_data, str):
                        task_id = await task_queue.add_text_task(task_data)
                    elif isinstance(task_data, dict):
                        task_id = await task_queue.add_json_task(task_data)
                    else:
                        continue
                    
                    if task_id:
                        loaded_count += 1
                        
                except Exception as e:
                    db_logger.logger.error(f"Error adding task: {e}")
            
            db_logger.logger.info(f"Loaded {loaded_count} tasks from {filename}")
            
        except Exception as e:
            db_logger.logger.error(f"Error loading tasks from file: {e}")
    
    def _should_run_checkpoint(self) -> bool:
        """Check if it's time for a weekly checkpoint."""
        if not self.last_checkpoint:
            # First checkpoint after configured days
            return (datetime.now() - self.uptime_start).days >= config.CHECKPOINT_DAYS
        
        # Regular checkpoints
        return (datetime.now() - self.last_checkpoint).days >= config.CHECKPOINT_DAYS
    
    async def _run_weekly_checkpoint(self):
        """Run weekly checkpoint and generate summary."""
        try:
            db_logger.logger.info("🏁 Starting weekly checkpoint...")
            
            # Pause workers
            await task_executor.pause_workers()
            agent_state['is_paused'] = True
            
            # Generate summary
            start_date = self.last_checkpoint or self.uptime_start
            end_date = datetime.now()
            
            report_path = summary_generator.generate_summary(start_date, end_date)
            
            # Log checkpoint completion
            self.last_checkpoint = datetime.now()
            db_logger.log_event('SYSTEM', 'SYSTEM', 'CHECKPOINT', 'INFO', 
                              f'Weekly checkpoint completed: {report_path}')
            
            # Update next checkpoint time
            next_checkpoint = self.last_checkpoint + timedelta(days=config.CHECKPOINT_DAYS)
            agent_state['checkpoint_due'] = next_checkpoint.isoformat()
            
            print("\n" + "="*50)
            print("🏁 WEEKLY CHECKPOINT COMPLETED")
            print(f"📄 Report saved to: {report_path}")
            print("⏸️  Agent paused - waiting for manual resume")
            print(f"🌐 Dashboard: http://{config.FLASK_HOST}:{config.FLASK_PORT}")
            print("="*50 + "\n")
            
            # Wait for manual resume (via CLI or web interface)
            while agent_state.get('is_paused', True):
                await asyncio.sleep(1)
            
            # Resume workers
            await task_executor.resume_workers()
            db_logger.logger.info("✅ Weekly checkpoint completed, resuming operations")
            
        except Exception as e:
            db_logger.logger.error(f"Error during weekly checkpoint: {e}")
            # Resume workers even if checkpoint failed
            await task_executor.resume_workers()
            agent_state['is_paused'] = False
    
    async def _save_system_state(self):
        """Save current system state for crash recovery."""
        try:
            worker_states = task_executor.get_worker_status()
            queue_stats = await task_queue.get_queue_stats()
            
            state_data = {
                'uptime_start': self.uptime_start.isoformat(),
                'last_checkpoint': self.last_checkpoint.isoformat() if self.last_checkpoint else None,
                'worker_states': worker_states,
                'queue_stats': queue_stats,
                'timestamp': datetime.now().isoformat()
            }
            
            # Save to database
            db_logger.save_system_state(worker_states, queue_stats)
            
            # Save to file as backup
            with open('state.json', 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            db_logger.logger.error(f"Error saving system state: {e}")
    
    async def _load_system_state(self):
        """Load previous system state for crash recovery."""
        try:
            # Try to load from database first
            db_state = db_logger.load_system_state()
            if db_state:
                db_logger.logger.info("Loaded system state from database")
                return
            
            # Fall back to file
            if Path('state.json').exists():
                with open('state.json') as f:
                    state_data = json.load(f)
                
                # Restore uptime start time
                if 'uptime_start' in state_data:
                    self.uptime_start = datetime.fromisoformat(state_data['uptime_start'])
                
                # Restore last checkpoint
                if state_data.get('last_checkpoint'):
                    self.last_checkpoint = datetime.fromisoformat(state_data['last_checkpoint'])
                
                db_logger.logger.info("Loaded system state from file")
                
        except Exception as e:
            db_logger.logger.error(f"Error loading system state: {e}")
    
    async def _shutdown(self):
        """Graceful shutdown of all components."""
        try:
            db_logger.logger.info("🛑 Shutting down Autonomous Coding Agent...")
            
            # Update agent state
            agent_state['is_running'] = False
            
            # Stop workers
            await task_executor.stop_workers()
            
            # Cancel background tasks
            if self.state_save_task:
                self.state_save_task.cancel()
            
            # Save final state
            await self._save_system_state()
            
            # Stop file watcher
            if self.file_observer:
                self.file_observer.stop()
                self.file_observer.join()
            
            self.is_running = False
            
            db_logger.logger.info("✅ Autonomous Coding Agent shutdown completed")
            
        except Exception as e:
            db_logger.logger.error(f"Error during shutdown: {e}")

async def main():
    """Main entry point."""
    try:
        # Create and start the agent
        agent = AutonomousAgent()
        agent.loop = asyncio.get_event_loop()
        
        await agent.start()
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        db_logger.logger.error(f"Fatal error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    # Set up event loop policy for Windows
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the main application
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 