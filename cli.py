#!/usr/bin/env python3
"""
Command-line interface for the Autonomous Coding Agent.
Allows adding tasks, checking status, and controlling the agent.
"""

import argparse
import asyncio
import json
import sys
import requests
from typing import Dict, Any, Optional
from pathlib import Path

from config import config
from queue_manager import task_queue, Task
from logger import db_logger

class AgentCLI:
    """Command-line interface for the autonomous coding agent."""
    
    def __init__(self):
        self.base_url = f"http://{config.FLASK_HOST}:{config.FLASK_PORT}"
    
    def check_server_running(self) -> bool:
        """Check if the Flask server is running."""
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    async def add_task_direct(self, description: str, priority: int = 0) -> Optional[str]:
        """Add task directly to the queue (when server is not running)."""
        try:
            # Initialize queue if needed
            await task_queue.initialize()
            
            # Create and add task
            task = Task.from_text(description, priority)
            success = await task_queue.put(task)
            
            if success:
                print(f"✅ Task added successfully: {task.task_id}")
                print(f"📝 Description: {description}")
                print(f"⚡ Priority: {priority}")
                return task.task_id
            else:
                print("❌ Failed to add task")
                return None
                
        except Exception as e:
            print(f"❌ Error adding task: {e}")
            return None
    
    def add_task_via_api(self, description: str, priority: int = 0) -> Optional[str]:
        """Add task via Flask API (when server is running)."""
        try:
            payload = {
                'description': description,
                'priority': priority
            }
            
            response = requests.post(
                f"{self.base_url}/api/task",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    task_id = result.get('task_id')
                    print(f"✅ Task added successfully: {task_id}")
                    print(f"📝 Description: {description}")
                    print(f"⚡ Priority: {priority}")
                    return task_id
                else:
                    print(f"❌ API Error: {result.get('error', 'Unknown error')}")
                    return None
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error calling API: {e}")
            return None
    
    async def get_status_direct(self) -> Dict[str, Any]:
        """Get status directly from components."""
        try:
            await task_queue.initialize()
            queue_stats = await task_queue.get_queue_stats()
            task_stats = db_logger.get_task_stats()
            
            return {
                'queue': queue_stats,
                'tasks': task_stats,
                'source': 'direct'
            }
        except Exception as e:
            return {'error': str(e), 'source': 'direct'}
    
    def get_status_via_api(self) -> Dict[str, Any]:
        """Get status via Flask API."""
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'HTTP {response.status_code}', 'source': 'api'}
                
        except Exception as e:
            return {'error': str(e), 'source': 'api'}
    
    def pause_resume_agent(self, action: str) -> bool:
        """Pause or resume the agent via API."""
        if not self.check_server_running():
            print("❌ Agent server is not running")
            return False
        
        try:
            payload = {'action': action}
            response = requests.post(
                f"{self.base_url}/api/pause",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"✅ {result.get('message', 'Action completed')}")
                    return True
                else:
                    print(f"❌ Error: {result.get('error', 'Unknown error')}")
                    return False
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def get_logs(self, limit: int = 20) -> None:
        """Get recent logs."""
        if not self.check_server_running():
            print("❌ Agent server is not running - showing local logs")
            self.show_local_logs(limit)
            return
        
        try:
            response = requests.get(
                f"{self.base_url}/api/logs?limit={limit}",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logs = result.get('logs', [])
                    self.display_logs(logs)
                else:
                    print(f"❌ Error: {result.get('error', 'Unknown error')}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def show_local_logs(self, limit: int = 20) -> None:
        """Show logs from local database."""
        try:
            logs = db_logger.get_recent_logs(limit)
            self.display_logs(logs)
        except Exception as e:
            print(f"❌ Error reading local logs: {e}")
    
    def display_logs(self, logs) -> None:
        """Display logs in a formatted way."""
        if not logs:
            print("📝 No logs available")
            return
        
        print(f"📝 Recent Logs ({len(logs)} entries):")
        print("=" * 80)
        
        for log in logs:
            timestamp = log.get('timestamp', 'Unknown')
            level = log.get('log_level', 'INFO')
            component = log.get('component', 'UNKNOWN')
            worker = log.get('worker_id', '')
            task = log.get('task_id', '')
            message = log.get('message', '')
            
            # Format timestamp
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M:%S')
            except:
                time_str = timestamp
            
            # Color coding for levels
            level_colors = {
                'ERROR': '🔴',
                'WARNING': '🟡', 
                'INFO': '🔵',
                'DEBUG': '⚪'
            }
            level_icon = level_colors.get(level, '⚪')
            
            print(f"{level_icon} {time_str} [{component}]", end="")
            if worker:
                print(f" ({worker})", end="")
            if task:
                print(f" {{{task[:8]}}}", end="")
            print(f" {message}")
        
        print("=" * 80)
    
    async def show_status(self) -> None:
        """Show current agent status."""
        print("🔍 Checking agent status...")
        
        # Try API first
        if self.check_server_running():
            print("✅ Agent server is running")
            status = self.get_status_via_api()
        else:
            print("⚠️  Agent server is not running - checking local state")
            status = await self.get_status_direct()
        
        if 'error' in status:
            print(f"❌ Error getting status: {status['error']}")
            return
        
        print("\n📊 Status Summary:")
        print("=" * 50)
        
        # Agent state
        if 'agent_state' in status:
            agent_state = status['agent_state']
            is_running = agent_state.get('is_running', False)
            is_paused = agent_state.get('is_paused', False)
            
            if is_paused:
                print("🚧 Agent Status: PAUSED")
            elif is_running:
                print("🟢 Agent Status: RUNNING")
            else:
                print("🔴 Agent Status: STOPPED")
        
        # Queue status
        if 'queue' in status:
            queue = status['queue']
            print(f"📋 Queue Size: {queue.get('queue_size', 0)}")
            print(f"📈 Total Tasks: {queue.get('total_tasks', 0)}")
            
            if 'task_stats' in queue:
                stats = queue['task_stats']
                print(f"   - Pending: {stats.get('pending', 0)}")
                print(f"   - Running: {stats.get('running', 0)}")
                print(f"   - Completed: {stats.get('completed', 0)}")
                print(f"   - Failed: {stats.get('failed', 0)}")
        
        # Worker status
        if 'workers' in status:
            workers = status['workers']
            print(f"👷 Workers: {workers.get('worker_count', 0)}")
            print(f"✅ Completed: {workers.get('total_completed', 0)}")
            print(f"❌ Failed: {workers.get('total_failed', 0)}")
        
        # Model status
        if 'models' in status:
            models = status['models']
            print("🧠 Models:")
            for model_type, model_status in models.items():
                status_icon = "✅" if model_status.get('available') else "❌"
                active_mark = " (ACTIVE)" if model_status.get('current') else ""
                print(f"   {status_icon} {model_type.title()}{active_mark}")
        
        print("=" * 50)
    
    def load_tasks_from_file(self, file_path: str) -> None:
        """Load tasks from a YAML or JSON file."""
        try:
            path = Path(file_path)
            if not path.exists():
                print(f"❌ File not found: {file_path}")
                return
            
            content = path.read_text()
            
            # Try to parse as JSON first, then YAML
            try:
                import json
                data = json.loads(content)
            except json.JSONDecodeError:
                try:
                    import yaml
                    data = yaml.safe_load(content)
                except ImportError:
                    print("❌ PyYAML not installed. Install with: pip install pyyaml")
                    return
                except yaml.YAMLError as e:
                    print(f"❌ YAML parsing error: {e}")
                    return
            
            # Process tasks
            if isinstance(data, list):
                tasks = data
            elif isinstance(data, dict) and 'tasks' in data:
                tasks = data['tasks']
            else:
                print("❌ Invalid file format. Expected list of tasks or dict with 'tasks' key")
                return
            
            print(f"📂 Loading {len(tasks)} tasks from {file_path}")
            
            for i, task_data in enumerate(tasks):
                if isinstance(task_data, str):
                    description = task_data
                    priority = 0
                elif isinstance(task_data, dict):
                    description = task_data.get('description', task_data.get('prompt', ''))
                    priority = task_data.get('priority', 0)
                else:
                    print(f"⚠️  Skipping invalid task {i+1}: {task_data}")
                    continue
                
                if not description:
                    print(f"⚠️  Skipping empty task {i+1}")
                    continue
                
                # Add task
                if self.check_server_running():
                    self.add_task_via_api(description, priority)
                else:
                    asyncio.run(self.add_task_direct(description, priority))
                
                print()  # Empty line between tasks
            
            print(f"✅ Finished loading tasks from {file_path}")
            
        except Exception as e:
            print(f"❌ Error loading tasks from file: {e}")
    
    def add_task_with_repo_via_api(self, description: str, repo_alias: str, priority: int = 0):
        """Add a task targeting a specific repository via API."""
        try:
            data = {
                'description': description,
                'target_repo': repo_alias,
                'priority': priority
            }
            
            response = requests.post(f"{self.base_url}/api/task/with-repo", 
                                   json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"✅ Task added successfully: {result.get('task_id')}")
                    print(f"📝 Description: {description}")
                    print(f"🗂️  Target Repository: {repo_alias}")
                    print(f"⚡ Priority: {priority}")
                else:
                    print(f"❌ Failed to add task: {result.get('error')}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
        
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
            print("💡 Make sure the agent is running")
    
    def connect_repository(self, repo_type: str, path_or_url: str, alias: str):
        """Connect to a repository."""
        if not self.check_server_running():
            print("❌ Agent server not running. Please start the agent first.")
            return
        
        try:
            data = {
                'type': repo_type.lower(),
                'alias': alias
            }
            
            if repo_type.lower() == 'github':
                data['url'] = path_or_url
            elif repo_type.lower() == 'local':
                data['path'] = path_or_url
            else:
                print(f"❌ Invalid repository type: {repo_type}. Use 'github' or 'local'")
                return
            
            response = requests.post(f"{self.base_url}/api/repositories/connect", 
                                   json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"✅ Successfully connected to repository '{alias}'")
                    print(f"📁 Local path: {result.get('local_path')}")
                    if repo_type.lower() == 'github':
                        print(f"🌐 Remote URL: {path_or_url}")
                else:
                    print(f"❌ Failed to connect: {result.get('error')}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
        
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
    
    def list_repositories(self):
        """List all connected repositories."""
        if not self.check_server_running():
            print("❌ Agent server not running. Please start the agent first.")
            return
        
        try:
            response = requests.get(f"{self.base_url}/api/repositories", timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    repos = result.get('repositories', {})
                    
                    if not repos:
                        print("📁 No repositories connected")
                        return
                    
                    print(f"📁 Connected Repositories ({len(repos)}):")
                    print("-" * 50)
                    
                    for alias, info in repos.items():
                        status = "🟢 Active" if info.get('active', True) else "🔴 Inactive"
                        repo_type = info.get('type', 'unknown')
                        
                        print(f"  {alias} ({repo_type}) - {status}")
                        print(f"    Path: {info.get('local_path', 'N/A')}")
                        
                        if 'url' in info:
                            print(f"    URL: {info['url']}")
                        
                        if 'branch' in info:
                            print(f"    Branch: {info['branch']}")
                        
                        connected_at = info.get('connected_at', 'Unknown')
                        print(f"    Connected: {connected_at}")
                        print()
                else:
                    print(f"❌ Failed to get repositories: {result.get('error')}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
        
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
    
    def scan_repository(self, alias: str):
        """Scan a repository for potential tasks."""
        if not self.check_server_running():
            print("❌ Agent server not running. Please start the agent first.")
            return
        
        try:
            response = requests.get(f"{self.base_url}/api/repositories/{alias}/scan", timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    tasks_found = result.get('tasks_found', [])
                    issues_found = result.get('issues_found', [])
                    summary = result.get('scan_summary', {})
                    
                    print(f"🔍 Scan Results for '{alias}':")
                    print("-" * 40)
                    print(f"📋 Tasks found: {summary.get('total_tasks', 0)}")
                    print(f"⚠️  Issues found: {summary.get('total_issues', 0)}")
                    print()
                    
                    if tasks_found:
                        print("📋 TODO/FIXME Comments:")
                        for task in tasks_found[:10]:  # Show first 10
                            print(f"  • {task['file']}:{task['line']} - {task['content']}")
                        if len(tasks_found) > 10:
                            print(f"  ... and {len(tasks_found) - 10} more")
                        print()
                    
                    if issues_found:
                        print("⚠️  Potential Issues:")
                        for issue in issues_found:
                            print(f"  • {issue['description']}")
                            print(f"    Suggested: {issue['suggested_task']}")
                        print()
                    
                    if not tasks_found and not issues_found:
                        print("✅ No issues or tasks found - repository looks good!")
                    
                else:
                    print(f"❌ Failed to scan repository: {result.get('error')}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
        
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
    
    def pull_repository(self, alias: str):
        """Pull updates from a repository."""
        if not self.check_server_running():
            print("❌ Agent server not running. Please start the agent first.")
            return
        
        try:
            response = requests.post(f"{self.base_url}/api/repositories/{alias}/pull", timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    pull_info = result.get('pull_info', [])
                    last_pull = result.get('last_pull', 'Unknown')
                    
                    print(f"✅ Successfully pulled updates for '{alias}'")
                    print(f"⏰ Last pull: {last_pull}")
                    
                    if pull_info:
                        print("📥 Pull information:")
                        for info in pull_info:
                            print(f"  • {info}")
                else:
                    print(f"❌ Failed to pull updates: {result.get('error')}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
        
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
    
    def push_repository(self, alias: str):
        """Push changes to a repository."""
        if not self.check_server_running():
            print("❌ Agent server not running. Please start the agent first.")
            return
        
        try:
            data = {'commit_message': f'Agent updates - {alias}'}
            response = requests.post(f"{self.base_url}/api/repositories/{alias}/push", 
                                   json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    commit_hash = result.get('commit_hash')
                    commit_message = result.get('commit_message')
                    
                    print(f"✅ Successfully pushed changes for '{alias}'")
                    if commit_hash:
                        print(f"📝 Commit: {commit_hash[:8]} - {commit_message}")
                    
                    push_info = result.get('push_info', [])
                    if push_info:
                        for info in push_info:
                            print(f"  📤 {info}")
                else:
                    message = result.get('message', result.get('error'))
                    print(f"ℹ️  {message}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
        
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
    
    def disconnect_repository(self, alias: str):
        """Disconnect from a repository."""
        if not self.check_server_running():
            print("❌ Agent server not running. Please start the agent first.")
            return
        
        try:
            response = requests.post(f"{self.base_url}/api/repositories/{alias}/disconnect", 
                                   json={}, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"✅ Successfully disconnected from repository '{alias}'")
                    print(f"ℹ️  {result.get('message')}")
                else:
                    print(f"❌ Failed to disconnect: {result.get('error')}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
        
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
    
    def show_tireless_reviewer_status(self):
        """Show Tireless Reviewer status."""
        if not self.check_server_running():
            print("❌ Agent server not running. Please start the agent first.")
            return
        
        try:
            response = requests.get(f"{self.base_url}/api/tireless-reviewer/status", timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    status = result.get('tireless_reviewer_status', {})
                    stats = status.get('stats', {})
                    
                    print("🔍 Tireless Reviewer Status:")
                    print("-" * 40)
                    print(f"Status: {'🟢 On Duty' if status.get('is_running') else '🔴 Off Duty'}")
                    print(f"Active Workers: {status.get('active_workers', 0)}")
                    print()
                    print("📊 Review Statistics:")
                    print(f"  Tasks Reviewed: {stats.get('tasks_reviewed', 0)}")
                    print(f"  Issues Discovered: {stats.get('issues_discovered', 0)}")
                    print(f"  Improvements Suggested: {stats.get('improvements_suggested', 0)}")
                    print(f"  Major Tasks Respected: {stats.get('major_tasks_respected', 0)}")
                    
                    last_review = stats.get('last_review')
                    if last_review:
                        print(f"  Last Review: {last_review}")
                    else:
                        print("  Last Review: Never")
                else:
                    print(f"❌ Failed to get Tireless Reviewer status: {result.get('error')}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
        
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
    
    def force_review_task(self, task_id: str):
        """Force review of a specific task by the Tireless Reviewer."""
        if not self.check_server_running():
            print("❌ Agent server not running. Please start the agent first.")
            return
        
        try:
            response = requests.post(f"{self.base_url}/api/tireless-reviewer/force/{task_id}", 
                                   timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"✅ Tireless Reviewer analysis completed for task {task_id}")
                    print(f"🔍 {result.get('message')}")
                else:
                    print(f"❌ Review failed: {result.get('error')}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
        
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
    
    def show_review_results(self, task_id: str):
        """Show Tireless Reviewer results for a task."""
        if not self.check_server_running():
            print("❌ Agent server not running. Please start the agent first.")
            return
        
        try:
            response = requests.get(f"{self.base_url}/api/tireless-reviewer/results/{task_id}", 
                                  timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    results = result.get('tireless_reviewer_results', [])
                    
                    if not results:
                        print(f"ℹ️  No Tireless Reviewer results found for task {task_id}")
                        return
                    
                    print(f"🔍 Tireless Reviewer Results for Task {task_id}:")
                    print("-" * 50)
                    
                    for review_result in results:
                        review_type = review_result['review_type']
                        issues = review_result['issues_found']
                        created_at = review_result['created_at']
                        
                        print(f"\n📋 {review_type.replace('_', ' ').title()} ({created_at}):")
                        
                        if issues:
                            for issue in issues:
                                print(f"  • {issue}")
                        else:
                            print("  ✅ No issues found")
                else:
                    print(f"❌ Failed to get Tireless Reviewer results: {result.get('error')}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
        
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic task management
  %(prog)s "Create a FastAPI health check endpoint"
  %(prog)s --priority 5 "Fix critical bug in authentication"
  %(prog)s --status
  %(prog)s --pause
  %(prog)s --resume
  %(prog)s --logs 50
  %(prog)s --load-tasks tasks.yaml
  
  # Repository management
  %(prog)s --connect-repo github https://github.com/user/repo.git myrepo
  %(prog)s --connect-repo local /path/to/project localproj
  %(prog)s --list-repos
  %(prog)s --scan-repo myrepo
  %(prog)s --pull-repo myrepo
  %(prog)s --push-repo myrepo
  
  # Task with repository targeting
  %(prog)s --repo myrepo "Add error handling to the API"
  
  # Tireless Reviewer (24/7 code quality guardian)
  %(prog)s --tireless-reviewer-status
  %(prog)s --force-review abc123de
  %(prog)s --review-results abc123de
        """
    )
    
    # Task addition
    parser.add_argument('description', nargs='?', help='Task description to add to queue')
    parser.add_argument('--priority', '-p', type=int, default=0, 
                       help='Task priority (0=normal, higher=more urgent)')
    
    # Status and control
    parser.add_argument('--status', '-s', action='store_true', 
                       help='Show current agent status')
    parser.add_argument('--pause', action='store_true', 
                       help='Pause the agent')
    parser.add_argument('--resume', action='store_true', 
                       help='Resume the agent')
    
    # Logs
    parser.add_argument('--logs', '-l', type=int, metavar='N', 
                       help='Show N recent log entries')
    
    # File operations
    parser.add_argument('--load-tasks', metavar='FILE', 
                       help='Load tasks from YAML/JSON file')
    
    # Repository management
    parser.add_argument('--connect-repo', nargs=3, metavar=('TYPE', 'PATH_OR_URL', 'ALIAS'),
                       help='Connect to repository: github <url> <alias> or local <path> <alias>')
    parser.add_argument('--list-repos', action='store_true',
                       help='List all connected repositories')
    parser.add_argument('--scan-repo', metavar='ALIAS',
                       help='Scan repository for potential tasks')
    parser.add_argument('--pull-repo', metavar='ALIAS',
                       help='Pull updates from repository')
    parser.add_argument('--push-repo', metavar='ALIAS',
                       help='Push changes to repository')
    parser.add_argument('--disconnect-repo', metavar='ALIAS',
                       help='Disconnect from repository')
    
    # Tireless Reviewer management
    parser.add_argument('--tireless-reviewer-status', action='store_true',
                       help='Show Tireless Reviewer status')
    parser.add_argument('--force-review', metavar='TASK_ID',
                       help='Force review of a specific completed task by the Tireless Reviewer')
    parser.add_argument('--review-results', metavar='TASK_ID',
                       help='Show Tireless Reviewer results for a task')
    
    # Task with repository
    parser.add_argument('--repo', metavar='ALIAS',
                       help='Target repository for the task')
    
    # Output format
    parser.add_argument('--json', action='store_true', 
                       help='Output in JSON format')
    parser.add_argument('--quiet', '-q', action='store_true', 
                       help='Minimal output')
    
    args = parser.parse_args()
    
    # Create CLI instance
    cli = AgentCLI()
    
    try:
        # Handle different commands
        if args.status:
            asyncio.run(cli.show_status())
        
        elif args.pause:
            cli.pause_resume_agent('pause')
        
        elif args.resume:
            cli.pause_resume_agent('resume')
        
        elif args.logs is not None:
            cli.get_logs(args.logs)
        
        elif args.load_tasks:
            cli.load_tasks_from_file(args.load_tasks)
        
        elif args.connect_repo:
            cli.connect_repository(args.connect_repo[0], args.connect_repo[1], args.connect_repo[2])
        
        elif args.list_repos:
            cli.list_repositories()
        
        elif args.scan_repo:
            cli.scan_repository(args.scan_repo)
        
        elif args.pull_repo:
            cli.pull_repository(args.pull_repo)
        
        elif args.push_repo:
            cli.push_repository(args.push_repo)
        
        elif args.disconnect_repo:
            cli.disconnect_repository(args.disconnect_repo)
        
        elif args.tireless_reviewer_status:
            cli.show_tireless_reviewer_status()
        
        elif args.force_review:
            cli.force_review_task(args.force_review)
        
        elif args.review_results:
            cli.show_review_results(args.review_results)
        
        elif args.description:
            # Add single task
            if cli.check_server_running():
                if args.repo:
                    cli.add_task_with_repo_via_api(args.description, args.repo, args.priority)
                else:
                    cli.add_task_via_api(args.description, args.priority)
            else:
                asyncio.run(cli.add_task_direct(args.description, args.priority))
        
        else:
            # No command specified, show help
            parser.print_help()
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 