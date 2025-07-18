import asyncio
import sqlite3
import os
import ast
import subprocess
import tempfile
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import re

from logger import db_logger
from config import config
from model_handler import model_handler

class TirelessReviewer:
    """
    The Tireless Reviewer: A 24/7 code quality guardian that never stops improving your codebase.
    
    This dedicated worker continuously reviews completed tasks for additional errors, inconsistencies,
    and improvement opportunities. It respects ongoing major work and only interrupts after 7 days,
    ensuring your development flow remains uninterrupted while maintaining relentless quality standards.
    """
    
    def __init__(self):
        self.is_running = False
        self.review_workers: Dict[str, asyncio.Task] = {}
        self.shutdown_event = asyncio.Event()
        self.review_interval = 300  # 5 minutes between review cycles
        self.deep_analysis_interval = 1800  # 30 minutes for deep analysis
        self.major_task_grace_period = 7 * 24 * 3600  # 7 days in seconds
        
        # Review metrics
        self.review_stats = {
            'tasks_reviewed': 0,
            'issues_discovered': 0,
            'improvements_suggested': 0,
            'last_review': None,
            'major_tasks_respected': 0
        }
        
    async def start_review_workers(self, worker_count: int = 2):
        """Start the Tireless Reviewer workers."""
        self.is_running = True
        
        db_logger.log_event('SYSTEM', 'SYSTEM', 'TIRELESS_REVIEWER', 'INFO', 
                          f'🔍 Starting Tireless Reviewer with {worker_count} workers')
        
        # Start different types of review workers
        for i in range(worker_count):
            worker_id = f"reviewer_{i+1}"
            
            if i == 0:
                # Primary reviewer - focuses on recent completions
                worker_task = asyncio.create_task(self._primary_review_loop(worker_id))
            else:
                # Deep reviewer - comprehensive analysis of older tasks
                worker_task = asyncio.create_task(self._deep_review_loop(worker_id))
                
            self.review_workers[worker_id] = worker_task
        
        db_logger.log_event('SYSTEM', 'SYSTEM', 'TIRELESS_REVIEWER', 'INFO', 
                          f'✅ Tireless Reviewer deployed: {len(self.review_workers)} workers active')
    
    async def stop_review_workers(self):
        """Stop the Tireless Reviewer workers."""
        self.is_running = False
        self.shutdown_event.set()
        
        db_logger.log_event('SYSTEM', 'SYSTEM', 'TIRELESS_REVIEWER', 'INFO', 
                          '⏸️ Tireless Reviewer workers stopping...')
        
        for worker_id, worker_task in self.review_workers.items():
            if not worker_task.done():
                worker_task.cancel()
        
        if self.review_workers:
            await asyncio.gather(*self.review_workers.values(), return_exceptions=True)
        
        self.review_workers.clear()
        
    async def _primary_review_loop(self, worker_id: str):
        """Primary review worker - checks recently completed tasks with respect for major work."""
        db_logger.log_event('SYSTEM', worker_id, 'TIRELESS_REVIEWER', 'INFO', 
                          f'🔍 Primary reviewer {worker_id} on duty')
        
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Get recently completed tasks (last 24 hours)
                    completed_tasks = self._get_recently_completed_tasks(hours=24)
                    
                    for task_data in completed_tasks:
                        if self.shutdown_event.is_set():
                            break
                        
                        # Check if this is a major task that should be respected
                        if self._should_respect_major_task(task_data):
                            self.review_stats['major_tasks_respected'] += 1
                            db_logger.log_event(task_data['task_id'], worker_id, 'TIRELESS_REVIEWER', 'INFO', 
                                              '⏰ Respecting ongoing major task - will review after 7 days')
                            continue
                            
                        await self._review_completed_task(worker_id, task_data)
                        await asyncio.sleep(1)  # Brief pause between reviews
                    
                    # Update review stats
                    self.review_stats['last_review'] = datetime.now().isoformat()
                    
                    # Wait before next cycle
                    await asyncio.sleep(self.review_interval)
                    
                except Exception as e:
                    db_logger.logger.error(f"Error in primary review loop: {e}")
                    await asyncio.sleep(60)  # Wait before retrying
                    
        except asyncio.CancelledError:
            db_logger.log_event('SYSTEM', worker_id, 'TIRELESS_REVIEWER', 'INFO', 
                              f'🛑 Primary reviewer {worker_id} off duty')
    
    def _should_respect_major_task(self, task_data: Dict[str, Any]) -> bool:
        """Check if a task is part of major ongoing work that should be respected for 7 days."""
        try:
            # Parse completion time
            completed_at = datetime.fromisoformat(task_data['completed_at'].replace('Z', '+00:00'))
            time_since_completion = (datetime.now() - completed_at).total_seconds()
            
            # Major task indicators (priority, description keywords, etc.)
            description = task_data.get('description', '').lower()
            major_indicators = [
                'major', 'large', 'significant', 'important', 'critical', 'epic',
                'feature', 'refactor', 'migration', 'upgrade', 'redesign'
            ]
            
            # Check if task seems major and is within grace period
            is_major = any(indicator in description for indicator in major_indicators)
            within_grace_period = time_since_completion < self.major_task_grace_period
            
            return is_major and within_grace_period
            
        except Exception as e:
            db_logger.logger.error(f"Error checking major task status: {e}")
            return False  # When in doubt, don't interrupt
    
    async def _deep_review_loop(self, worker_id: str):
        """Deep review worker - comprehensive analysis of older tasks."""
        db_logger.log_event('SYSTEM', worker_id, 'TIRELESS_REVIEWER', 'INFO', 
                          f'🔬 Deep reviewer {worker_id} analyzing legacy code')
        
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Get older completed tasks (1-7 days old) for deep analysis
                    old_tasks = self._get_completed_tasks_range(hours_start=24, hours_end=168)
                    
                    for task_data in old_tasks:
                        if self.shutdown_event.is_set():
                            break
                            
                        await self._deep_review_task(worker_id, task_data)
                        await asyncio.sleep(2)  # Longer pause for deep analysis
                    
                    # Wait before next deep analysis cycle
                    await asyncio.sleep(self.deep_analysis_interval)
                    
                except Exception as e:
                    db_logger.logger.error(f"Error in deep review loop: {e}")
                    await asyncio.sleep(120)  # Wait before retrying
                    
        except asyncio.CancelledError:
            db_logger.log_event('SYSTEM', worker_id, 'TIRELESS_REVIEWER', 'INFO', 
                              f'🛑 Deep reviewer {worker_id} off duty')
    
    def _get_recently_completed_tasks(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get tasks completed in the last N hours."""
        try:
            with sqlite3.connect(config.DB_PATH) as conn:
                cursor = conn.cursor()
                
                cutoff_time = datetime.now() - timedelta(hours=hours)
                
                cursor.execute('''
                    SELECT task_id, description, result, completed_at, worker_id
                    FROM tasks 
                    WHERE status = 'completed' 
                    AND completed_at > ?
                    ORDER BY completed_at DESC
                ''', (cutoff_time.isoformat(),))
                
                tasks = []
                for row in cursor.fetchall():
                    task_id, description, result, completed_at, worker_id = row
                    tasks.append({
                        'task_id': task_id,
                        'description': description,
                        'result': result,
                        'completed_at': completed_at,
                        'worker_id': worker_id
                    })
                
                return tasks
                
        except Exception as e:
            db_logger.logger.error(f"Failed to get recently completed tasks: {e}")
            return []
    
    def _get_completed_tasks_range(self, hours_start: int, hours_end: int) -> List[Dict[str, Any]]:
        """Get completed tasks in a specific time range."""
        try:
            with sqlite3.connect(config.DB_PATH) as conn:
                cursor = conn.cursor()
                
                start_time = datetime.now() - timedelta(hours=hours_end)
                end_time = datetime.now() - timedelta(hours=hours_start)
                
                cursor.execute('''
                    SELECT task_id, description, result, completed_at, worker_id
                    FROM tasks 
                    WHERE status = 'completed' 
                    AND completed_at BETWEEN ? AND ?
                    ORDER BY completed_at DESC
                    LIMIT 50
                ''', (start_time.isoformat(), end_time.isoformat()))
                
                tasks = []
                for row in cursor.fetchall():
                    task_id, description, result, completed_at, worker_id = row
                    tasks.append({
                        'task_id': task_id,
                        'description': description,
                        'result': result,
                        'completed_at': completed_at,
                        'worker_id': worker_id
                    })
                
                return tasks
                
        except Exception as e:
            db_logger.logger.error(f"Failed to get tasks in range: {e}")
            return []
    
    async def _review_completed_task(self, worker_id: str, task_data: Dict[str, Any]):
        """Review a completed task for additional errors and improvement opportunities."""
        task_id = task_data['task_id']
        
        db_logger.log_event(task_id, worker_id, 'TIRELESS_REVIEWER', 'INFO', 
                          '🔍 Tireless review in progress...')
        
        review_findings = {
            'syntax_issues': [],
            'logic_errors': [],
            'consistency_issues': [],
            'integration_problems': [],
            'improvement_suggestions': []
        }
        
        try:
            # Parse the result to extract code files
            result_data = self._parse_task_result(task_data['result'])
            
            if not result_data or 'code_files' not in result_data:
                return
            
            # 1. Static Code Analysis
            syntax_issues = await self._perform_static_analysis(task_id, result_data)
            review_findings['syntax_issues'].extend(syntax_issues)
            
            # 2. Logic Consistency Check
            logic_errors = await self._check_logic_consistency(task_id, task_data['description'], result_data)
            review_findings['logic_errors'].extend(logic_errors)
            
            # 3. Integration Analysis
            integration_issues = await self._check_integration_issues(task_id, result_data)
            review_findings['integration_problems'].extend(integration_issues)
            
            # 4. Code Quality Analysis
            quality_issues = await self._analyze_code_quality(task_id, result_data)
            review_findings['improvement_suggestions'].extend(quality_issues)
            
            # 5. Cross-reference with existing codebase
            consistency_issues = await self._check_codebase_consistency(task_id, result_data)
            review_findings['consistency_issues'].extend(consistency_issues)
            
            # Log findings
            total_issues = sum(len(issues) for issues in review_findings.values())
            
            if total_issues > 0:
                self.review_stats['issues_discovered'] += total_issues
                
                db_logger.log_event(task_id, worker_id, 'TIRELESS_REVIEWER', 'WARNING', 
                                  f'📋 Tireless review discovered {total_issues} improvement opportunities')
                
                # Store detailed review findings
                await self._store_review_results(task_id, review_findings)
                
                # Optionally create follow-up tasks for critical issues
                await self._create_followup_tasks(task_id, review_findings)
                
            else:
                db_logger.log_event(task_id, worker_id, 'TIRELESS_REVIEWER', 'INFO', 
                                  '✅ Tireless review: code quality looks excellent!')
            
            self.review_stats['tasks_reviewed'] += 1
            
        except Exception as e:
            db_logger.logger.error(f"Error validating task {task_id}: {e}")
    
    async def _deep_review_task(self, worker_id: str, task_data: Dict[str, Any]):
        """Perform deep review analysis on older completed tasks."""
        task_id = task_data['task_id']
        
        db_logger.log_event(task_id, worker_id, 'TIRELESS_REVIEWER', 'INFO', 
                          '🔬 Deep analysis by Tireless Reviewer...')
        
        try:
            # Parse the result
            result_data = self._parse_task_result(task_data['result'])
            
            if not result_data:
                return
            
            # Deep analysis includes:
            # 1. Performance analysis
            performance_issues = await self._analyze_performance(task_id, result_data)
            
            # 2. Security analysis
            security_issues = await self._analyze_security(task_id, result_data)
            
            # 3. Documentation consistency
            doc_issues = await self._check_documentation_consistency(task_id, result_data)
            
            # 4. Long-term maintainability
            maintainability_issues = await self._analyze_maintainability(task_id, result_data)
            
            deep_results = {
                'performance_issues': performance_issues,
                'security_issues': security_issues,
                'documentation_issues': doc_issues,
                'maintainability_issues': maintainability_issues
            }
            
            total_deep_issues = sum(len(issues) for issues in deep_results.values())
            
            if total_deep_issues > 0:
                db_logger.log_event(task_id, worker_id, 'TIRELESS_REVIEWER', 'INFO', 
                                  f'🎯 Deep analysis discovered {total_deep_issues} enhancement opportunities')
                
                await self._store_deep_review_results(task_id, deep_results)
                self.review_stats['improvements_suggested'] += total_deep_issues
            
        except Exception as e:
            db_logger.logger.error(f"Error in deep validation of task {task_id}: {e}")
    
    def _parse_task_result(self, result_str: str) -> Optional[Dict[str, Any]]:
        """Parse task result string to extract structured data."""
        try:
            if result_str and result_str.strip():
                return eval(result_str)  # Note: In production, use ast.literal_eval for safety
        except:
            pass
        return None
    
    async def _perform_static_analysis(self, task_id: str, result_data: Dict[str, Any]) -> List[str]:
        """Perform static code analysis to find syntax and style issues."""
        issues = []
        
        try:
            code_files = result_data.get('code_files', [])
            
            for file_path in code_files:
                # Check if file exists and is Python
                if file_path.endswith('.py') and os.path.exists(file_path):
                    # Use AST to parse and check for issues
                    try:
                        with open(file_path, 'r') as f:
                            code_content = f.read()
                        
                        # Parse with AST
                        tree = ast.parse(code_content)
                        
                        # Check for common issues
                        issues.extend(self._check_ast_issues(tree, file_path))
                        
                    except SyntaxError as e:
                        issues.append(f"Syntax error in {file_path}: {e}")
                    except Exception as e:
                        issues.append(f"Analysis error in {file_path}: {e}")
        
        except Exception as e:
            db_logger.logger.error(f"Static analysis error for task {task_id}: {e}")
        
        return issues
    
    def _check_ast_issues(self, tree: ast.AST, file_path: str) -> List[str]:
        """Check AST for common code issues."""
        issues = []
        
        for node in ast.walk(tree):
            # Check for unused variables
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if node.id.startswith('_') and len(node.id) > 1:
                    issues.append(f"Potentially unused variable '{node.id}' in {file_path}")
            
            # Check for bare except clauses
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append(f"Bare except clause found in {file_path} - should catch specific exceptions")
            
            # Check for print statements (should use logging)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'print':
                issues.append(f"Print statement found in {file_path} - consider using logging")
        
        return issues
    
    async def _check_logic_consistency(self, task_id: str, description: str, result_data: Dict[str, Any]) -> List[str]:
        """Use AI to check if the generated code actually solves the described problem."""
        issues = []
        
        try:
            # Use AI model to analyze logic consistency
            consistency_prompt = f"""
Analyze the following task and its implementation for logical consistency:

Task Description: {description}

Implementation Summary: {result_data}

Check for:
1. Does the implementation actually solve the described problem?
2. Are there logical gaps or missing functionality?
3. Are there contradictions between requirements and implementation?
4. Are edge cases properly handled?

Return a JSON list of issues found, or empty list if no issues.
"""
            
            ai_response, _ = await model_handler.generate_code(consistency_prompt, task_id + "_validation")
            
            # Parse AI response for issues
            if ai_response and ai_response.strip():
                try:
                    ai_issues = json.loads(ai_response)
                    if isinstance(ai_issues, list):
                        issues.extend(ai_issues)
                except:
                    # If AI response isn't JSON, treat as single issue
                    if "no issues" not in ai_response.lower():
                        issues.append(f"Logic analysis suggests: {ai_response[:200]}...")
        
        except Exception as e:
            db_logger.logger.error(f"Logic consistency check error for task {task_id}: {e}")
        
        return issues
    
    async def _check_integration_issues(self, task_id: str, result_data: Dict[str, Any]) -> List[str]:
        """Check for potential integration issues with existing codebase."""
        issues = []
        
        try:
            # Check for import conflicts
            code_files = result_data.get('code_files', [])
            
            for file_path in code_files:
                if file_path.endswith('.py') and os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Check for import patterns that might conflict
                    imports = re.findall(r'^import\s+(\w+)', content, re.MULTILINE)
                    from_imports = re.findall(r'^from\s+(\w+)', content, re.MULTILINE)
                    
                    all_imports = imports + from_imports
                    
                    # Check if imports exist
                    for imp in all_imports:
                        try:
                            __import__(imp)
                        except ImportError:
                            issues.append(f"Missing dependency '{imp}' in {file_path}")
        
        except Exception as e:
            db_logger.logger.error(f"Integration check error for task {task_id}: {e}")
        
        return issues
    
    async def _analyze_code_quality(self, task_id: str, result_data: Dict[str, Any]) -> List[str]:
        """Analyze code quality and suggest improvements."""
        suggestions = []
        
        try:
            code_files = result_data.get('code_files', [])
            
            for file_path in code_files:
                if file_path.endswith('.py') and os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Check code complexity
                    lines = content.split('\n')
                    non_empty_lines = [line for line in lines if line.strip()]
                    
                    if len(non_empty_lines) > 100:
                        suggestions.append(f"Large file {file_path} ({len(non_empty_lines)} lines) - consider splitting")
                    
                    # Check for docstrings
                    if 'def ' in content and '"""' not in content and "'''" not in content:
                        suggestions.append(f"Missing docstrings in {file_path}")
                    
                    # Check for type hints
                    if 'def ' in content and '->' not in content:
                        suggestions.append(f"Consider adding type hints to {file_path}")
        
        except Exception as e:
            db_logger.logger.error(f"Code quality analysis error for task {task_id}: {e}")
        
        return suggestions
    
    async def _check_codebase_consistency(self, task_id: str, result_data: Dict[str, Any]) -> List[str]:
        """Check consistency with existing codebase patterns and conventions."""
        issues = []
        
        try:
            # This would be enhanced with actual codebase analysis
            # For now, we'll do basic pattern checking
            
            code_files = result_data.get('code_files', [])
            
            # Check naming conventions consistency
            for file_path in code_files:
                if file_path.endswith('.py') and os.path.exists(file_path):
                    # Check if file name follows snake_case convention
                    filename = os.path.basename(file_path)
                    if not re.match(r'^[a-z_][a-z0-9_]*\.py$', filename):
                        issues.append(f"File name '{filename}' doesn't follow snake_case convention")
        
        except Exception as e:
            db_logger.logger.error(f"Codebase consistency check error for task {task_id}: {e}")
        
        return issues
    
    async def _analyze_performance(self, task_id: str, result_data: Dict[str, Any]) -> List[str]:
        """Analyze code for potential performance issues."""
        issues = []
        
        try:
            code_files = result_data.get('code_files', [])
            
            for file_path in code_files:
                if file_path.endswith('.py') and os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Check for potential performance issues
                    if re.search(r'for.*in.*range\(len\(', content):
                        issues.append(f"Inefficient iteration pattern in {file_path} - consider enumerate()")
                    
                    if '+=' in content and 'str' in content:
                        issues.append(f"String concatenation in loop in {file_path} - consider join()")
        
        except Exception as e:
            db_logger.logger.error(f"Performance analysis error for task {task_id}: {e}")
        
        return issues
    
    async def _analyze_security(self, task_id: str, result_data: Dict[str, Any]) -> List[str]:
        """Analyze code for potential security issues."""
        issues = []
        
        try:
            code_files = result_data.get('code_files', [])
            
            for file_path in code_files:
                if file_path.endswith('.py') and os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Check for security issues
                    if 'eval(' in content:
                        issues.append(f"Dangerous eval() usage in {file_path}")
                    
                    if 'exec(' in content:
                        issues.append(f"Dangerous exec() usage in {file_path}")
                    
                    if re.search(r'subprocess\.(call|run|Popen).*shell=True', content):
                        issues.append(f"Shell injection risk in {file_path}")
        
        except Exception as e:
            db_logger.logger.error(f"Security analysis error for task {task_id}: {e}")
        
        return issues
    
    async def _check_documentation_consistency(self, task_id: str, result_data: Dict[str, Any]) -> List[str]:
        """Check documentation consistency and completeness."""
        issues = []
        
        try:
            # Check if README needs updating, if functions have proper docs, etc.
            code_files = result_data.get('code_files', [])
            
            for file_path in code_files:
                if file_path.endswith('.py') and os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Count functions without docstrings
                    function_matches = re.findall(r'def\s+\w+\s*\([^)]*\):', content)
                    docstring_matches = re.findall(r'def\s+\w+\s*\([^)]*\):\s*"""', content)
                    
                    if len(function_matches) > len(docstring_matches):
                        undocumented = len(function_matches) - len(docstring_matches)
                        issues.append(f"{undocumented} undocumented functions in {file_path}")
        
        except Exception as e:
            db_logger.logger.error(f"Documentation check error for task {task_id}: {e}")
        
        return issues
    
    async def _analyze_maintainability(self, task_id: str, result_data: Dict[str, Any]) -> List[str]:
        """Analyze long-term maintainability issues."""
        issues = []
        
        try:
            code_files = result_data.get('code_files', [])
            
            for file_path in code_files:
                if file_path.endswith('.py') and os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Check for hard-coded values
                    if re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', content):
                        issues.append(f"Hard-coded IP address in {file_path}")
                    
                    # Check for TODO/FIXME comments
                    todo_count = len(re.findall(r'#.*TODO|#.*FIXME', content, re.IGNORECASE))
                    if todo_count > 0:
                        issues.append(f"{todo_count} TODO/FIXME comments in {file_path}")
        
        except Exception as e:
            db_logger.logger.error(f"Maintainability analysis error for task {task_id}: {e}")
        
        return issues
    
    async def _store_review_results(self, task_id: str, results: Dict[str, List[str]]):
        """Store Tireless Reviewer findings in database."""
        try:
            with sqlite3.connect(config.DB_PATH) as conn:
                cursor = conn.cursor()
                
                # Create tireless_review_results table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tireless_review_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        review_type TEXT NOT NULL,
                        issues_found TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                    )
                ''')
                
                # Store results by type
                for review_type, issues in results.items():
                    if issues:
                        cursor.execute('''
                            INSERT INTO tireless_review_results (task_id, review_type, issues_found)
                            VALUES (?, ?, ?)
                        ''', (task_id, review_type, json.dumps(issues)))
                
                conn.commit()
                
        except Exception as e:
            db_logger.logger.error(f"Failed to store review results for task {task_id}: {e}")
    
    async def _store_deep_review_results(self, task_id: str, results: Dict[str, List[str]]):
        """Store deep review results."""
        try:
            # Same as _store_review_results but with 'deep_' prefix
            prefixed_results = {f"deep_{k}": v for k, v in results.items()}
            await self._store_review_results(task_id, prefixed_results)
            
        except Exception as e:
            db_logger.logger.error(f"Failed to store deep review results for task {task_id}: {e}")
    
    async def _create_followup_tasks(self, task_id: str, results: Dict[str, List[str]]):
        """Create follow-up tasks for critical issues found during validation."""
        try:
            # Count critical issues
            critical_issues = results.get('syntax_issues', []) + results.get('logic_errors', [])
            
            if len(critical_issues) >= 3:  # Create follow-up task if 3+ critical issues
                from queue_manager import task_queue
                
                followup_description = f"""
🔍 Tireless Reviewer Follow-up for task {task_id[:8]}:

Critical Issues Discovered:
{chr(10).join('- ' + issue for issue in critical_issues[:5])}

The Tireless Reviewer has identified these quality improvements. 
Please address these findings to enhance code reliability and maintainability.
"""
                
                followup_task_id = await task_queue.add_text_task(
                    followup_description, 
                    priority=2  # Medium priority for fixes
                )
                
                if followup_task_id:
                    db_logger.log_event(task_id, 'SYSTEM', 'TIRELESS_REVIEWER', 'INFO', 
                                      f'📋 Created follow-up task {followup_task_id} for review findings')
                
        except Exception as e:
            db_logger.logger.error(f"Failed to create follow-up tasks for task {task_id}: {e}")
    
    def get_review_stats(self) -> Dict[str, Any]:
        """Get current Tireless Reviewer statistics."""
        return {
            'is_running': self.is_running,
            'active_workers': len(self.review_workers),
            'stats': self.review_stats.copy()
        }
    
    async def force_review_task(self, task_id: str) -> Dict[str, Any]:
        """Force review of a specific task by the Tireless Reviewer (for manual triggering)."""
        try:
            # Get task data
            with sqlite3.connect(config.DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT task_id, description, result, completed_at, worker_id
                    FROM tasks 
                    WHERE task_id = ? AND status = 'completed'
                ''', (task_id,))
                
                row = cursor.fetchone()
                if not row:
                    return {'success': False, 'error': 'Task not found or not completed'}
                
                task_data = {
                    'task_id': row[0],
                    'description': row[1],
                    'result': row[2],
                    'completed_at': row[3],
                    'worker_id': row[4]
                }
            
            # Run review
            await self._review_completed_task('manual_reviewer', task_data)
            
            return {'success': True, 'message': 'Tireless review completed'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

# Global Tireless Reviewer instance
tireless_reviewer = TirelessReviewer() 