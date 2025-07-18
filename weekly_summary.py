"""
Weekly Summary Generator for the Autonomous Coding Agent.
Generates comprehensive markdown reports for weekly checkpoints.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from pathlib import Path

from logger import db_logger
from git_manager import git_manager
from config import config

class WeeklySummaryGenerator:
    """Generates weekly summary reports for the autonomous coding agent."""
    
    def __init__(self):
        self.db_path = config.DB_PATH
        self.output_dir = Path("reports")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_summary(self, start_date: datetime = None, end_date: datetime = None) -> str:
        """Generate a comprehensive weekly summary report."""
        if end_date is None:
            end_date = datetime.now()
        
        if start_date is None:
            start_date = end_date - timedelta(days=7)
        
        # Collect data
        task_stats = self._get_task_statistics(start_date, end_date)
        model_stats = self._get_model_statistics(start_date, end_date)
        git_stats = self._get_git_statistics(start_date, end_date)
        error_analysis = self._get_error_analysis(start_date, end_date)
        performance_metrics = self._get_performance_metrics(start_date, end_date)
        
        # Generate markdown report
        report = self._generate_markdown_report(
            start_date, end_date, task_stats, model_stats, 
            git_stats, error_analysis, performance_metrics
        )
        
        # Save report
        filename = f"weekly_summary_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.md"
        report_path = self.output_dir / filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        db_logger.logger.info(f"Weekly summary generated: {report_path}")
        return str(report_path)
    
    def _get_task_statistics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get task statistics for the period."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Overall task counts
                cursor.execute('''
                    SELECT status, COUNT(*) as count 
                    FROM tasks 
                    WHERE created_at BETWEEN ? AND ?
                    GROUP BY status
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                status_counts = dict(cursor.fetchall())
                
                # Task completion times
                cursor.execute('''
                    SELECT 
                        AVG((julianday(completed_at) - julianday(started_at)) * 24 * 60) as avg_duration_minutes,
                        COUNT(*) as completed_count
                    FROM tasks 
                    WHERE completed_at BETWEEN ? AND ?
                    AND started_at IS NOT NULL AND completed_at IS NOT NULL
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                duration_result = cursor.fetchone()
                avg_duration = duration_result[0] if duration_result[0] else 0
                completed_count = duration_result[1]
                
                # Daily task breakdown
                cursor.execute('''
                    SELECT 
                        DATE(created_at) as date,
                        status,
                        COUNT(*) as count
                    FROM tasks 
                    WHERE created_at BETWEEN ? AND ?
                    GROUP BY DATE(created_at), status
                    ORDER BY date
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                daily_breakdown = {}
                for row in cursor.fetchall():
                    date, status, count = row
                    if date not in daily_breakdown:
                        daily_breakdown[date] = {}
                    daily_breakdown[date][status] = count
                
                # Most common task types (based on keywords in descriptions)
                cursor.execute('''
                    SELECT description FROM tasks 
                    WHERE created_at BETWEEN ? AND ?
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                descriptions = [row[0] for row in cursor.fetchall()]
                task_types = self._analyze_task_types(descriptions)
                
                return {
                    'status_counts': status_counts,
                    'avg_duration_minutes': round(avg_duration, 2),
                    'completed_count': completed_count,
                    'daily_breakdown': daily_breakdown,
                    'task_types': task_types,
                    'total_tasks': sum(status_counts.values())
                }
                
        except Exception as e:
            db_logger.logger.error(f"Error getting task statistics: {e}")
            return {}
    
    def _get_model_statistics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get AI model usage statistics for the period."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Model usage by type
                cursor.execute('''
                    SELECT 
                        model_type,
                        model_name,
                        COUNT(*) as request_count,
                        AVG(response_time) as avg_response_time,
                        SUM(prompt_tokens) as total_prompt_tokens,
                        SUM(completion_tokens) as total_completion_tokens
                    FROM model_stats 
                    WHERE timestamp BETWEEN ? AND ?
                    GROUP BY model_type, model_name
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                model_usage = []
                for row in cursor.fetchall():
                    model_type, model_name, count, avg_time, prompt_tokens, completion_tokens = row
                    model_usage.append({
                        'type': model_type,
                        'name': model_name,
                        'requests': count,
                        'avg_response_time': round(avg_time, 2) if avg_time else 0,
                        'prompt_tokens': prompt_tokens or 0,
                        'completion_tokens': completion_tokens or 0
                    })
                
                # Daily model usage
                cursor.execute('''
                    SELECT 
                        DATE(timestamp) as date,
                        model_type,
                        COUNT(*) as count
                    FROM model_stats 
                    WHERE timestamp BETWEEN ? AND ?
                    GROUP BY DATE(timestamp), model_type
                    ORDER BY date
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                daily_usage = {}
                for row in cursor.fetchall():
                    date, model_type, count = row
                    if date not in daily_usage:
                        daily_usage[date] = {}
                    daily_usage[date][model_type] = count
                
                return {
                    'model_usage': model_usage,
                    'daily_usage': daily_usage,
                    'total_requests': sum(usage['requests'] for usage in model_usage)
                }
                
        except Exception as e:
            db_logger.logger.error(f"Error getting model statistics: {e}")
            return {}
    
    def _get_git_statistics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get Git repository statistics for the period."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Commit counts
                cursor.execute('''
                    SELECT COUNT(*) as commit_count
                    FROM git_commits 
                    WHERE timestamp BETWEEN ? AND ?
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                commit_count = cursor.fetchone()[0]
                
                # Files changed
                cursor.execute('''
                    SELECT files_changed FROM git_commits 
                    WHERE timestamp BETWEEN ? AND ?
                    AND files_changed IS NOT NULL
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                all_files = []
                for row in cursor.fetchall():
                    try:
                        files = json.loads(row[0])
                        all_files.extend(files)
                    except:
                        continue
                
                # Count file types
                file_types = {}
                for file_path in all_files:
                    ext = Path(file_path).suffix.lower()
                    if ext:
                        file_types[ext] = file_types.get(ext, 0) + 1
                
                # Daily commit activity
                cursor.execute('''
                    SELECT 
                        DATE(timestamp) as date,
                        COUNT(*) as count
                    FROM git_commits 
                    WHERE timestamp BETWEEN ? AND ?
                    GROUP BY DATE(timestamp)
                    ORDER BY date
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                daily_commits = dict(cursor.fetchall())
                
                # Get recent commits from git manager
                recent_commits = git_manager.get_recent_commits(20)
                
                return {
                    'commit_count': commit_count,
                    'files_changed_count': len(all_files),
                    'unique_files_count': len(set(all_files)),
                    'file_types': file_types,
                    'daily_commits': daily_commits,
                    'recent_commits': recent_commits[:10]  # Last 10 commits
                }
                
        except Exception as e:
            db_logger.logger.error(f"Error getting git statistics: {e}")
            return {}
    
    def _get_error_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze errors and failures for the period."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Failed tasks with error messages
                cursor.execute('''
                    SELECT error_message, COUNT(*) as count
                    FROM tasks 
                    WHERE status = 'failed'
                    AND completed_at BETWEEN ? AND ?
                    AND error_message IS NOT NULL
                    GROUP BY error_message
                    ORDER BY count DESC
                    LIMIT 10
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                common_errors = []
                for row in cursor.fetchall():
                    error_msg, count = row
                    common_errors.append({
                        'error': error_msg[:100] + '...' if len(error_msg) > 100 else error_msg,
                        'count': count
                    })
                
                # Error trends by component
                cursor.execute('''
                    SELECT 
                        component,
                        COUNT(*) as error_count
                    FROM execution_logs 
                    WHERE log_level = 'ERROR'
                    AND timestamp BETWEEN ? AND ?
                    GROUP BY component
                    ORDER BY error_count DESC
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                component_errors = dict(cursor.fetchall())
                
                # Retry statistics
                cursor.execute('''
                    SELECT 
                        AVG(retry_count) as avg_retries,
                        MAX(retry_count) as max_retries,
                        COUNT(*) as tasks_with_retries
                    FROM tasks 
                    WHERE retry_count > 0
                    AND created_at BETWEEN ? AND ?
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                retry_stats = cursor.fetchone()
                
                return {
                    'common_errors': common_errors,
                    'component_errors': component_errors,
                    'avg_retries': round(retry_stats[0], 2) if retry_stats[0] else 0,
                    'max_retries': retry_stats[1] or 0,
                    'tasks_with_retries': retry_stats[2] or 0
                }
                
        except Exception as e:
            db_logger.logger.error(f"Error analyzing errors: {e}")
            return {}
    
    def _get_performance_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get performance metrics for the period."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Task throughput (tasks per hour)
                total_hours = (end_date - start_date).total_seconds() / 3600
                
                cursor.execute('''
                    SELECT COUNT(*) FROM tasks 
                    WHERE completed_at BETWEEN ? AND ?
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                completed_tasks = cursor.fetchone()[0]
                throughput = completed_tasks / total_hours if total_hours > 0 else 0
                
                # Success rate
                cursor.execute('''
                    SELECT 
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                        COUNT(*) as total
                    FROM tasks 
                    WHERE created_at BETWEEN ? AND ?
                    AND status IN ('completed', 'failed')
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                result = cursor.fetchone()
                completed, failed, total = result
                success_rate = (completed / total * 100) if total > 0 else 0
                
                # Peak activity hours
                cursor.execute('''
                    SELECT 
                        strftime('%H', created_at) as hour,
                        COUNT(*) as count
                    FROM tasks 
                    WHERE created_at BETWEEN ? AND ?
                    GROUP BY strftime('%H', created_at)
                    ORDER BY count DESC
                    LIMIT 5
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                peak_hours = [(int(row[0]), row[1]) for row in cursor.fetchall()]
                
                return {
                    'throughput_per_hour': round(throughput, 2),
                    'success_rate': round(success_rate, 2),
                    'total_completed': completed,
                    'total_failed': failed,
                    'peak_hours': peak_hours
                }
                
        except Exception as e:
            db_logger.logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def _analyze_task_types(self, descriptions: List[str]) -> Dict[str, int]:
        """Analyze task types based on keywords in descriptions."""
        keywords = {
            'api': ['api', 'endpoint', 'rest', 'fastapi', 'flask'],
            'web': ['web', 'html', 'css', 'javascript', 'frontend', 'ui'],
            'database': ['database', 'sql', 'sqlite', 'postgres', 'mongo'],
            'test': ['test', 'testing', 'pytest', 'unittest'],
            'fix': ['fix', 'bug', 'error', 'debug', 'issue'],
            'feature': ['feature', 'add', 'create', 'implement', 'new'],
            'refactor': ['refactor', 'optimize', 'improve', 'cleanup'],
            'documentation': ['doc', 'readme', 'comment', 'document']
        }
        
        task_types = {}
        
        for description in descriptions:
            desc_lower = description.lower()
            for task_type, words in keywords.items():
                if any(word in desc_lower for word in words):
                    task_types[task_type] = task_types.get(task_type, 0) + 1
                    break  # Only count each task once
        
        return dict(sorted(task_types.items(), key=lambda x: x[1], reverse=True))
    
    def _generate_markdown_report(self, start_date: datetime, end_date: datetime,
                                task_stats: Dict, model_stats: Dict, git_stats: Dict,
                                error_analysis: Dict, performance_metrics: Dict) -> str:
        """Generate the markdown report."""
        
        report = f"""# 🤖 Autonomous Coding Agent - Weekly Summary

**Report Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}  
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📊 Executive Summary

"""
        
        # Add executive summary
        total_tasks = task_stats.get('total_tasks', 0)
        completed_tasks = performance_metrics.get('total_completed', 0)
        success_rate = performance_metrics.get('success_rate', 0)
        commit_count = git_stats.get('commit_count', 0)
        
        report += f"""
- **Total Tasks Processed:** {total_tasks}
- **Tasks Completed:** {completed_tasks}
- **Success Rate:** {success_rate}%
- **Git Commits:** {commit_count}
- **Throughput:** {performance_metrics.get('throughput_per_hour', 0)} tasks/hour
"""
        
        # Task Statistics
        report += "\n---\n\n## 📋 Task Statistics\n\n"
        
        if task_stats.get('status_counts'):
            report += "### Task Status Breakdown\n\n"
            for status, count in task_stats['status_counts'].items():
                report += f"- **{status.title()}:** {count}\n"
        
        if task_stats.get('task_types'):
            report += "\n### Task Types\n\n"
            for task_type, count in task_stats['task_types'].items():
                report += f"- **{task_type.title()}:** {count}\n"
        
        if task_stats.get('daily_breakdown'):
            report += "\n### Daily Activity\n\n"
            report += "| Date | Pending | Running | Completed | Failed |\n"
            report += "|------|---------|---------|-----------|--------|\n"
            
            for date, stats in task_stats['daily_breakdown'].items():
                pending = stats.get('pending', 0)
                running = stats.get('running', 0)
                completed = stats.get('completed', 0)
                failed = stats.get('failed', 0)
                report += f"| {date} | {pending} | {running} | {completed} | {failed} |\n"
        
        # Performance Metrics
        report += "\n---\n\n## 📈 Performance Metrics\n\n"
        
        avg_duration = task_stats.get('avg_duration_minutes', 0)
        report += f"- **Average Task Duration:** {avg_duration} minutes\n"
        report += f"- **Peak Activity Hours:** {', '.join([f'{hour}:00 ({count} tasks)' for hour, count in performance_metrics.get('peak_hours', [])])}\n"
        
        # AI Model Usage
        report += "\n---\n\n## 🧠 AI Model Usage\n\n"
        
        if model_stats.get('model_usage'):
            report += "### Model Statistics\n\n"
            report += "| Model Type | Model Name | Requests | Avg Response Time | Tokens Used |\n"
            report += "|------------|------------|----------|-------------------|-------------|\n"
            
            for usage in model_stats['model_usage']:
                total_tokens = usage['prompt_tokens'] + usage['completion_tokens']
                report += f"| {usage['type']} | {usage['name']} | {usage['requests']} | {usage['avg_response_time']}s | {total_tokens} |\n"
        
        # Git Activity
        report += "\n---\n\n## 📦 Git Repository Activity\n\n"
        
        report += f"- **Total Commits:** {git_stats.get('commit_count', 0)}\n"
        report += f"- **Files Changed:** {git_stats.get('files_changed_count', 0)}\n"
        report += f"- **Unique Files Modified:** {git_stats.get('unique_files_count', 0)}\n"
        
        if git_stats.get('file_types'):
            report += "\n### File Types Modified\n\n"
            for ext, count in git_stats['file_types'].items():
                report += f"- **{ext}:** {count} changes\n"
        
        if git_stats.get('recent_commits'):
            report += "\n### Recent Commits\n\n"
            for commit in git_stats['recent_commits']:
                report += f"- `{commit['short_hash']}` {commit['message'][:60]}{'...' if len(commit['message']) > 60 else ''}\n"
        
        # Error Analysis
        report += "\n---\n\n## ⚠️ Error Analysis\n\n"
        
        if error_analysis.get('common_errors'):
            report += "### Most Common Errors\n\n"
            for error in error_analysis['common_errors']:
                report += f"- **{error['count']} occurrences:** {error['error']}\n"
        
        if error_analysis.get('component_errors'):
            report += "\n### Errors by Component\n\n"
            for component, count in error_analysis['component_errors'].items():
                report += f"- **{component}:** {count} errors\n"
        
        retry_stats = error_analysis
        if retry_stats.get('tasks_with_retries', 0) > 0:
            report += f"\n### Retry Statistics\n\n"
            report += f"- **Tasks Requiring Retries:** {retry_stats['tasks_with_retries']}\n"
            report += f"- **Average Retries:** {retry_stats['avg_retries']}\n"
            report += f"- **Maximum Retries:** {retry_stats['max_retries']}\n"
        
        # Recommendations
        report += "\n---\n\n## 💡 Recommendations\n\n"
        
        recommendations = []
        
        if success_rate < 80:
            recommendations.append("- **Low Success Rate:** Consider reviewing task complexity or model performance")
        
        if error_analysis.get('component_errors'):
            top_error_component = max(error_analysis['component_errors'].items(), key=lambda x: x[1])
            recommendations.append(f"- **High Error Rate:** Focus on improving {top_error_component[0]} component")
        
        if performance_metrics.get('throughput_per_hour', 0) < 1:
            recommendations.append("- **Low Throughput:** Consider increasing worker count or optimizing task processing")
        
        if not recommendations:
            recommendations.append("- **System Performance:** Overall system performance is within expected parameters")
        
        for rec in recommendations:
            report += rec + "\n"
        
        # Footer
        report += f"\n---\n\n*Report generated by Autonomous Coding Agent v1.0*  \n*Total uptime: {(end_date - start_date).days} days*\n"
        
        return report

# Global summary generator instance
summary_generator = WeeklySummaryGenerator() 