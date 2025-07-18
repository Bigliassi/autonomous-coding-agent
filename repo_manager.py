import git
import os
import shutil
import tempfile
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import json

from logger import db_logger
from config import config

class RepositoryManager:
    """
    Manages connections to external repositories and folders for workers to operate on.
    Allows the agent to work on multiple repositories simultaneously.
    """
    
    def __init__(self):
        self.connected_repos: Dict[str, Dict[str, Any]] = {}
        self.working_directories: Dict[str, str] = {}
        self.repos_config_file = "connected_repos.json"
        self.base_repos_dir = "connected_repositories"
        
        # Ensure base directory exists
        os.makedirs(self.base_repos_dir, exist_ok=True)
        
        # Load existing connections
        self._load_repo_connections()
    
    def _load_repo_connections(self):
        """Load previously connected repositories from config file."""
        try:
            if os.path.exists(self.repos_config_file):
                with open(self.repos_config_file, 'r') as f:
                    config_data = json.load(f)
                    self.connected_repos = config_data.get('repositories', {})
                    
                db_logger.logger.info(f"Loaded {len(self.connected_repos)} repository connections")
        except Exception as e:
            db_logger.logger.error(f"Failed to load repository connections: {e}")
            self.connected_repos = {}
    
    def _save_repo_connections(self):
        """Save current repository connections to config file."""
        try:
            config_data = {
                'repositories': self.connected_repos,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.repos_config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
                
        except Exception as e:
            db_logger.logger.error(f"Failed to save repository connections: {e}")
    
    async def connect_to_github_repo(self, repo_url: str, alias: str = None, branch: str = "main") -> Dict[str, Any]:
        """
        Connect to a GitHub repository by cloning it locally.
        
        Args:
            repo_url: GitHub repository URL (https://github.com/owner/repo.git)
            alias: Optional alias for the repository
            branch: Branch to checkout (default: main)
        
        Returns:
            Dict with connection status and details
        """
        try:
            # Extract repo name from URL
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            alias = alias or repo_name
            
            # Check if already connected
            if alias in self.connected_repos:
                return {
                    'success': False,
                    'error': f'Repository alias "{alias}" already exists',
                    'existing_repo': self.connected_repos[alias]
                }
            
            # Create local directory for this repo
            local_path = os.path.join(self.base_repos_dir, alias)
            
            # Clone the repository
            db_logger.log_event('SYSTEM', 'SYSTEM', 'REPO_MANAGER', 'INFO', 
                              f'Cloning repository {repo_url} to {local_path}')
            
            try:
                repo = git.Repo.clone_from(repo_url, local_path, branch=branch)
                
                # Store connection info
                self.connected_repos[alias] = {
                    'url': repo_url,
                    'local_path': local_path,
                    'branch': branch,
                    'type': 'github',
                    'connected_at': datetime.now().isoformat(),
                    'last_pull': datetime.now().isoformat(),
                    'active': True
                }
                
                self.working_directories[alias] = local_path
                self._save_repo_connections()
                
                db_logger.log_event('SYSTEM', 'SYSTEM', 'REPO_MANAGER', 'INFO', 
                                  f'Successfully connected to repository {alias}')
                
                return {
                    'success': True,
                    'alias': alias,
                    'local_path': local_path,
                    'repo_info': self.connected_repos[alias]
                }
                
            except git.GitCommandError as e:
                return {
                    'success': False,
                    'error': f'Git clone failed: {str(e)}'
                }
                
        except Exception as e:
            db_logger.logger.error(f"Failed to connect to GitHub repo {repo_url}: {e}")
            return {
                'success': False,
                'error': f'Connection failed: {str(e)}'
            }
    
    async def connect_to_local_folder(self, folder_path: str, alias: str = None, initialize_git: bool = False) -> Dict[str, Any]:
        """
        Connect to a local folder for workers to operate on.
        
        Args:
            folder_path: Path to the local folder
            alias: Optional alias for the folder
            initialize_git: Whether to initialize Git if not present
        
        Returns:
            Dict with connection status and details
        """
        try:
            folder_path = os.path.abspath(folder_path)
            
            if not os.path.exists(folder_path):
                return {
                    'success': False,
                    'error': f'Folder does not exist: {folder_path}'
                }
            
            if not os.path.isdir(folder_path):
                return {
                    'success': False,
                    'error': f'Path is not a directory: {folder_path}'
                }
            
            # Generate alias from folder name if not provided
            alias = alias or os.path.basename(folder_path)
            
            # Check if already connected
            if alias in self.connected_repos:
                return {
                    'success': False,
                    'error': f'Repository alias "{alias}" already exists',
                    'existing_repo': self.connected_repos[alias]
                }
            
            # Check if it's a Git repository
            is_git_repo = False
            repo = None
            try:
                repo = git.Repo(folder_path)
                is_git_repo = True
            except git.InvalidGitRepositoryError:
                if initialize_git:
                    try:
                        repo = git.Repo.init(folder_path)
                        is_git_repo = True
                        db_logger.log_event('SYSTEM', 'SYSTEM', 'REPO_MANAGER', 'INFO', 
                                          f'Initialized Git repository in {folder_path}')
                    except Exception as e:
                        db_logger.logger.warning(f"Failed to initialize Git in {folder_path}: {e}")
            
            # Store connection info
            self.connected_repos[alias] = {
                'local_path': folder_path,
                'type': 'local_folder',
                'connected_at': datetime.now().isoformat(),
                'is_git_repo': is_git_repo,
                'active': True
            }
            
            if is_git_repo and repo:
                try:
                    # Get current branch
                    current_branch = repo.active_branch.name
                    self.connected_repos[alias]['branch'] = current_branch
                    
                    # Get remote info if available
                    if repo.remotes:
                        remote_url = list(repo.remote().urls)[0]
                        self.connected_repos[alias]['remote_url'] = remote_url
                except:
                    pass  # Ignore errors getting Git info
            
            self.working_directories[alias] = folder_path
            self._save_repo_connections()
            
            db_logger.log_event('SYSTEM', 'SYSTEM', 'REPO_MANAGER', 'INFO', 
                              f'Successfully connected to local folder {alias}')
            
            return {
                'success': True,
                'alias': alias,
                'local_path': folder_path,
                'is_git_repo': is_git_repo,
                'repo_info': self.connected_repos[alias]
            }
            
        except Exception as e:
            db_logger.logger.error(f"Failed to connect to local folder {folder_path}: {e}")
            return {
                'success': False,
                'error': f'Connection failed: {str(e)}'
            }
    
    async def pull_repo_updates(self, alias: str) -> Dict[str, Any]:
        """Pull latest updates from a connected repository."""
        try:
            if alias not in self.connected_repos:
                return {
                    'success': False,
                    'error': f'Repository "{alias}" not found'
                }
            
            repo_info = self.connected_repos[alias]
            local_path = repo_info['local_path']
            
            if not repo_info.get('is_git_repo', True):
                return {
                    'success': False,
                    'error': f'Repository "{alias}" is not a Git repository'
                }
            
            try:
                repo = git.Repo(local_path)
                
                # Check if remote exists
                if not repo.remotes:
                    return {
                        'success': False,
                        'error': f'No remote configured for repository "{alias}"'
                    }
                
                # Pull updates
                origin = repo.remotes.origin
                pull_info = origin.pull()
                
                # Update last pull time
                self.connected_repos[alias]['last_pull'] = datetime.now().isoformat()
                self._save_repo_connections()
                
                db_logger.log_event('SYSTEM', 'SYSTEM', 'REPO_MANAGER', 'INFO', 
                                  f'Pulled updates for repository {alias}')
                
                return {
                    'success': True,
                    'pull_info': [str(info) for info in pull_info],
                    'last_pull': self.connected_repos[alias]['last_pull']
                }
                
            except git.GitCommandError as e:
                return {
                    'success': False,
                    'error': f'Git pull failed: {str(e)}'
                }
                
        except Exception as e:
            db_logger.logger.error(f"Failed to pull updates for repo {alias}: {e}")
            return {
                'success': False,
                'error': f'Pull failed: {str(e)}'
            }
    
    async def push_repo_changes(self, alias: str, commit_message: str = None) -> Dict[str, Any]:
        """Push changes to a connected repository."""
        try:
            if alias not in self.connected_repos:
                return {
                    'success': False,
                    'error': f'Repository "{alias}" not found'
                }
            
            repo_info = self.connected_repos[alias]
            local_path = repo_info['local_path']
            
            if not repo_info.get('is_git_repo', True):
                return {
                    'success': False,
                    'error': f'Repository "{alias}" is not a Git repository'
                }
            
            try:
                repo = git.Repo(local_path)
                
                # Check if there are changes to commit
                if not repo.is_dirty() and not repo.untracked_files:
                    return {
                        'success': True,
                        'message': 'No changes to push'
                    }
                
                # Add all changes
                repo.git.add(A=True)
                
                # Commit changes
                commit_message = commit_message or f"Agent updates - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                commit = repo.index.commit(commit_message)
                
                # Push to remote
                if repo.remotes:
                    origin = repo.remotes.origin
                    push_info = origin.push()
                    
                    db_logger.log_event('SYSTEM', 'SYSTEM', 'REPO_MANAGER', 'INFO', 
                                      f'Pushed changes for repository {alias}')
                    
                    return {
                        'success': True,
                        'commit_hash': commit.hexsha,
                        'commit_message': commit_message,
                        'push_info': [str(info) for info in push_info]
                    }
                else:
                    return {
                        'success': True,
                        'commit_hash': commit.hexsha,
                        'commit_message': commit_message,
                        'message': 'Committed locally (no remote configured)'
                    }
                
            except git.GitCommandError as e:
                return {
                    'success': False,
                    'error': f'Git operation failed: {str(e)}'
                }
                
        except Exception as e:
            db_logger.logger.error(f"Failed to push changes for repo {alias}: {e}")
            return {
                'success': False,
                'error': f'Push failed: {str(e)}'
            }
    
    def get_repo_working_directory(self, alias: str) -> Optional[str]:
        """Get the working directory for a connected repository."""
        return self.working_directories.get(alias)
    
    def list_connected_repos(self) -> Dict[str, Dict[str, Any]]:
        """List all connected repositories."""
        return self.connected_repos.copy()
    
    def get_repo_info(self, alias: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific connected repository."""
        return self.connected_repos.get(alias)
    
    async def disconnect_repo(self, alias: str, remove_local: bool = False) -> Dict[str, Any]:
        """
        Disconnect from a repository.
        
        Args:
            alias: Repository alias
            remove_local: Whether to remove local files (for cloned repos)
        
        Returns:
            Dict with operation status
        """
        try:
            if alias not in self.connected_repos:
                return {
                    'success': False,
                    'error': f'Repository "{alias}" not found'
                }
            
            repo_info = self.connected_repos[alias]
            local_path = repo_info['local_path']
            
            # Remove from tracking
            del self.connected_repos[alias]
            if alias in self.working_directories:
                del self.working_directories[alias]
            
            # Remove local files if requested and it's a cloned repo
            if remove_local and repo_info.get('type') == 'github':
                try:
                    shutil.rmtree(local_path)
                    db_logger.log_event('SYSTEM', 'SYSTEM', 'REPO_MANAGER', 'INFO', 
                                      f'Removed local files for repository {alias}')
                except Exception as e:
                    db_logger.logger.warning(f"Failed to remove local files for {alias}: {e}")
            
            self._save_repo_connections()
            
            db_logger.log_event('SYSTEM', 'SYSTEM', 'REPO_MANAGER', 'INFO', 
                              f'Disconnected from repository {alias}')
            
            return {
                'success': True,
                'message': f'Disconnected from repository "{alias}"'
            }
            
        except Exception as e:
            db_logger.logger.error(f"Failed to disconnect from repo {alias}: {e}")
            return {
                'success': False,
                'error': f'Disconnect failed: {str(e)}'
            }
    
    async def scan_repo_for_tasks(self, alias: str) -> Dict[str, Any]:
        """
        Scan a connected repository for potential tasks (TODOs, FIXMEs, etc.).
        
        Args:
            alias: Repository alias
        
        Returns:
            Dict with found tasks and suggestions
        """
        try:
            if alias not in self.connected_repos:
                return {
                    'success': False,
                    'error': f'Repository "{alias}" not found'
                }
            
            repo_info = self.connected_repos[alias]
            local_path = repo_info['local_path']
            
            tasks_found = []
            
            # Scan for TODO/FIXME comments
            for root, dirs, files in os.walk(local_path):
                # Skip hidden directories and common non-source directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'build', 'dist']]
                
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.md')):
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, local_path)
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = f.readlines()
                                
                                for line_num, line in enumerate(lines, 1):
                                    line_lower = line.lower()
                                    if any(keyword in line_lower for keyword in ['todo', 'fixme', 'hack', 'bug']):
                                        tasks_found.append({
                                            'file': relative_path,
                                            'line': line_num,
                                            'content': line.strip(),
                                            'type': 'comment_task'
                                        })
                        except Exception as e:
                            continue  # Skip files that can't be read
            
            # Look for common issues
            issues_found = []
            
            # Check for missing requirements.txt in Python projects
            if any(f.endswith('.py') for f in os.listdir(local_path) if os.path.isfile(os.path.join(local_path, f))):
                if not os.path.exists(os.path.join(local_path, 'requirements.txt')):
                    issues_found.append({
                        'type': 'missing_file',
                        'description': 'Python project missing requirements.txt',
                        'suggested_task': 'Create requirements.txt file with project dependencies'
                    })
            
            # Check for missing README
            readme_files = [f for f in os.listdir(local_path) if f.lower().startswith('readme')]
            if not readme_files:
                issues_found.append({
                    'type': 'missing_file',
                    'description': 'Project missing README file',
                    'suggested_task': 'Create comprehensive README.md file'
                })
            
            db_logger.log_event('SYSTEM', 'SYSTEM', 'REPO_MANAGER', 'INFO', 
                              f'Scanned repository {alias}: found {len(tasks_found)} tasks, {len(issues_found)} issues')
            
            return {
                'success': True,
                'tasks_found': tasks_found,
                'issues_found': issues_found,
                'scan_summary': {
                    'total_tasks': len(tasks_found),
                    'total_issues': len(issues_found),
                    'scanned_at': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            db_logger.logger.error(f"Failed to scan repo {alias} for tasks: {e}")
            return {
                'success': False,
                'error': f'Scan failed: {str(e)}'
            }
    
    async def get_repo_file_structure(self, alias: str, max_depth: int = 3) -> Dict[str, Any]:
        """Get the file structure of a connected repository."""
        try:
            if alias not in self.connected_repos:
                return {
                    'success': False,
                    'error': f'Repository "{alias}" not found'
                }
            
            repo_info = self.connected_repos[alias]
            local_path = repo_info['local_path']
            
            def build_tree(path, current_depth=0):
                if current_depth >= max_depth:
                    return None
                
                items = []
                try:
                    for item in sorted(os.listdir(path)):
                        if item.startswith('.'):
                            continue
                            
                        item_path = os.path.join(path, item)
                        
                        if os.path.isdir(item_path):
                            subtree = build_tree(item_path, current_depth + 1)
                            items.append({
                                'name': item,
                                'type': 'directory',
                                'children': subtree
                            })
                        else:
                            items.append({
                                'name': item,
                                'type': 'file',
                                'size': os.path.getsize(item_path)
                            })
                except PermissionError:
                    pass
                
                return items
            
            file_structure = build_tree(local_path)
            
            return {
                'success': True,
                'alias': alias,
                'structure': file_structure,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            db_logger.logger.error(f"Failed to get file structure for repo {alias}: {e}")
            return {
                'success': False,
                'error': f'Failed to get file structure: {str(e)}'
            }
    
    def set_repo_active_status(self, alias: str, active: bool) -> bool:
        """Set the active status of a repository (for enabling/disabling workers on it)."""
        try:
            if alias in self.connected_repos:
                self.connected_repos[alias]['active'] = active
                self._save_repo_connections()
                
                status = "activated" if active else "deactivated"
                db_logger.log_event('SYSTEM', 'SYSTEM', 'REPO_MANAGER', 'INFO', 
                                  f'Repository {alias} {status}')
                return True
        except Exception as e:
            db_logger.logger.error(f"Failed to set active status for repo {alias}: {e}")
        
        return False
    
    def get_active_repos(self) -> List[str]:
        """Get list of currently active repository aliases."""
        return [alias for alias, info in self.connected_repos.items() if info.get('active', True)]

# Global repository manager instance
repo_manager = RepositoryManager() 