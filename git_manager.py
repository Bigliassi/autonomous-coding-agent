import git
import os
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
from logger import db_logger
from config import config

class GitManager:
    """Handles Git operations for the autonomous coding agent."""
    
    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.repo = None
        self.branch = config.GIT_BRANCH
        self.auto_push = config.GIT_AUTO_PUSH
        self._ensure_git_repo()
    
    def _ensure_git_repo(self):
        """Ensure we have a valid Git repository."""
        try:
            # Try to open existing repo
            self.repo = git.Repo(self.repo_path)
            db_logger.logger.info(f"Using existing Git repository at {self.repo_path}")
            
        except git.InvalidGitRepositoryError:
            try:
                # Initialize new repo
                self.repo = git.Repo.init(self.repo_path)
                db_logger.logger.info(f"Initialized new Git repository at {self.repo_path}")
                
                # Create initial commit if no commits exist
                if not list(self.repo.iter_commits()):
                    self._create_initial_commit()
                    
            except Exception as e:
                db_logger.logger.error(f"Failed to initialize Git repository: {e}")
                self.repo = None
        
        except Exception as e:
            db_logger.logger.error(f"Git repository error: {e}")
            self.repo = None
    
    def _create_initial_commit(self):
        """Create an initial commit with basic files."""
        try:
            # Create a basic .gitignore if it doesn't exist
            gitignore_path = os.path.join(self.repo_path, '.gitignore')
            if not os.path.exists(gitignore_path):
                gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Agent specific
agent.log
db/
state.json
.env
"""
                with open(gitignore_path, 'w') as f:
                    f.write(gitignore_content)
            
            # Add files and commit
            self.repo.index.add(['.gitignore'])
            self.repo.index.commit("Initial commit - Autonomous coding agent setup")
            
            db_logger.logger.info("Created initial Git commit")
            
        except Exception as e:
            db_logger.logger.error(f"Failed to create initial commit: {e}")
    
    def is_available(self) -> bool:
        """Check if Git operations are available."""
        return self.repo is not None
    
    def get_current_branch(self) -> str:
        """Get the current branch name."""
        if not self.is_available():
            return "unknown"
        
        try:
            return self.repo.active_branch.name
        except Exception:
            return "detached"
    
    def create_or_switch_branch(self, branch_name: str) -> bool:
        """Create or switch to a branch."""
        if not self.is_available():
            return False
        
        try:
            # Check if branch exists
            if branch_name in [branch.name for branch in self.repo.branches]:
                # Switch to existing branch
                self.repo.git.checkout(branch_name)
                db_logger.logger.info(f"Switched to existing branch: {branch_name}")
            else:
                # Create new branch
                new_branch = self.repo.create_head(branch_name)
                new_branch.checkout()
                db_logger.logger.info(f"Created and switched to new branch: {branch_name}")
            
            self.branch = branch_name
            return True
            
        except Exception as e:
            db_logger.logger.error(f"Failed to create/switch branch {branch_name}: {e}")
            return False
    
    def stage_files(self, file_paths: List[str]) -> bool:
        """Stage files for commit."""
        if not self.is_available():
            return False
        
        try:
            # Convert to relative paths
            relative_paths = []
            for file_path in file_paths:
                if os.path.isabs(file_path):
                    rel_path = os.path.relpath(file_path, self.repo_path)
                else:
                    rel_path = file_path
                
                # Check if file exists
                full_path = os.path.join(self.repo_path, rel_path)
                if os.path.exists(full_path):
                    relative_paths.append(rel_path)
                else:
                    db_logger.logger.warning(f"File not found for staging: {full_path}")
            
            if relative_paths:
                self.repo.index.add(relative_paths)
                db_logger.logger.info(f"Staged {len(relative_paths)} files")
                return True
            else:
                db_logger.logger.warning("No valid files to stage")
                return False
                
        except Exception as e:
            db_logger.logger.error(f"Failed to stage files: {e}")
            return False
    
    def commit_changes(self, task_id: str, message: str = None, file_paths: List[str] = None) -> Tuple[bool, Optional[str]]:
        """Commit staged changes."""
        if not self.is_available():
            return False, None
        
        try:
            # Stage files if provided
            if file_paths:
                if not self.stage_files(file_paths):
                    return False, None
            
            # Check if there are changes to commit
            if not self.repo.is_dirty(index=True):
                db_logger.log_event(task_id, 'GIT_MANAGER', 'GIT_MANAGER', 'INFO', 
                                  'No changes to commit')
                return True, None  # No changes is not an error
            
            # Generate commit message if not provided
            if not message:
                message = f"Autonomous agent task: {task_id[:8]}"
            
            # Add timestamp and task info
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_message = f"{message}\n\nTask ID: {task_id}\nTimestamp: {timestamp}\nGenerated by: Autonomous Coding Agent"
            
            # Commit changes
            commit = self.repo.index.commit(commit_message)
            commit_hash = commit.hexsha
            
            # Get list of changed files
            changed_files = list(self.repo.index.diff("HEAD~1").iter_change_type('A')) + \
                           list(self.repo.index.diff("HEAD~1").iter_change_type('M'))
            file_names = [item.a_path for item in changed_files]
            
            # Log the commit
            db_logger.log_git_commit(task_id, commit_hash, commit_message, file_names)
            db_logger.log_event(task_id, 'GIT_MANAGER', 'GIT_MANAGER', 'INFO', 
                              f'Committed changes: {commit_hash[:8]}')
            
            return True, commit_hash
            
        except Exception as e:
            error_msg = f"Failed to commit changes: {e}"
            db_logger.log_event(task_id, 'GIT_MANAGER', 'GIT_MANAGER', 'ERROR', error_msg)
            return False, None
    
    def push_changes(self, task_id: str, remote: str = 'origin', branch: str = None) -> bool:
        """Push changes to remote repository."""
        if not self.is_available() or not self.auto_push:
            return True  # Not pushing is not an error if auto_push is disabled
        
        branch = branch or self.branch
        
        try:
            # Check if remote exists
            if remote not in [r.name for r in self.repo.remotes]:
                db_logger.log_event(task_id, 'GIT_MANAGER', 'GIT_MANAGER', 'WARNING', 
                                  f'Remote {remote} not found, skipping push')
                return True
            
            # Push to remote
            origin = self.repo.remote(remote)
            push_info = origin.push(f"{branch}:{branch}")
            
            # Check push result
            for info in push_info:
                if info.flags & info.ERROR:
                    error_msg = f"Push failed: {info.summary}"
                    db_logger.log_event(task_id, 'GIT_MANAGER', 'GIT_MANAGER', 'ERROR', error_msg)
                    return False
            
            db_logger.log_event(task_id, 'GIT_MANAGER', 'GIT_MANAGER', 'INFO', 
                              f'Pushed changes to {remote}/{branch}')
            return True
            
        except Exception as e:
            error_msg = f"Failed to push changes: {e}"
            db_logger.log_event(task_id, 'GIT_MANAGER', 'GIT_MANAGER', 'ERROR', error_msg)
            return False
    
    def write_and_commit_code(self, task_id: str, code_files: Dict[str, str], 
                             commit_message: str = None) -> Tuple[bool, Optional[str]]:
        """Write code files and commit them."""
        if not self.is_available():
            return False, None
        
        try:
            written_files = []
            
            # Write code files
            for filename, code in code_files.items():
                file_path = os.path.join(self.repo_path, filename)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Write file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                
                written_files.append(filename)
                db_logger.log_event(task_id, 'GIT_MANAGER', 'GIT_MANAGER', 'INFO', 
                                  f'Wrote file: {filename}')
            
            # Commit the changes
            if not commit_message:
                commit_message = f"Generated code for task {task_id[:8]}"
            
            success, commit_hash = self.commit_changes(task_id, commit_message, written_files)
            
            if success and commit_hash:
                # Push if auto-push is enabled
                if self.auto_push:
                    self.push_changes(task_id)
            
            return success, commit_hash
            
        except Exception as e:
            error_msg = f"Failed to write and commit code: {e}"
            db_logger.log_event(task_id, 'GIT_MANAGER', 'GIT_MANAGER', 'ERROR', error_msg)
            return False, None
    
    def get_recent_commits(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent commits."""
        if not self.is_available():
            return []
        
        try:
            commits = []
            for commit in self.repo.iter_commits(max_count=limit):
                commits.append({
                    'hash': commit.hexsha,
                    'short_hash': commit.hexsha[:8],
                    'message': commit.message.strip(),
                    'author': str(commit.author),
                    'timestamp': commit.committed_datetime.isoformat(),
                    'files_changed': len(commit.stats.files)
                })
            return commits
            
        except Exception as e:
            db_logger.logger.error(f"Failed to get recent commits: {e}")
            return []
    
    def get_repository_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        if not self.is_available():
            return {
                'available': False,
                'error': 'Git repository not available'
            }
        
        try:
            # Count commits
            commit_count = sum(1 for _ in self.repo.iter_commits())
            
            # Get branch info
            branches = [branch.name for branch in self.repo.branches]
            current_branch = self.get_current_branch()
            
            # Check for uncommitted changes
            has_staged = self.repo.is_dirty(index=True)
            has_unstaged = self.repo.is_dirty(working_tree=True)
            
            # Get remote info
            remotes = [remote.name for remote in self.repo.remotes]
            
            return {
                'available': True,
                'commit_count': commit_count,
                'current_branch': current_branch,
                'branches': branches,
                'has_staged_changes': has_staged,
                'has_unstaged_changes': has_unstaged,
                'remotes': remotes,
                'auto_push_enabled': self.auto_push
            }
            
        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }
    
    def setup_github_remote(self, username: str, repo_name: str, token: str = None) -> bool:
        """Setup GitHub remote repository."""
        if not self.is_available():
            return False
        
        try:
            github_url = f"https://github.com/{username}/{repo_name}.git"
            
            # Add token to URL if provided
            if token:
                github_url = f"https://{token}@github.com/{username}/{repo_name}.git"
            
            # Remove existing origin if it exists
            if 'origin' in [r.name for r in self.repo.remotes]:
                self.repo.delete_remote('origin')
            
            # Add new origin
            origin = self.repo.create_remote('origin', github_url)
            
            db_logger.logger.info(f"Added GitHub remote: {github_url}")
            return True
            
        except Exception as e:
            db_logger.logger.error(f"Failed to setup GitHub remote: {e}")
            return False

# Global git manager instance
git_manager = GitManager() 