from flask import Flask, render_template, request, jsonify, Response
import asyncio
import json
from datetime import datetime
from typing import Dict, Any
import threading
import time

from config import config
from logger import db_logger
from queue_manager import task_queue
from task_executor import task_executor
from model_handler import model_handler
from git_manager import git_manager

app = Flask(__name__)

# Global state for the agent
agent_state = {
    'is_running': False,
    'is_paused': False,
    'uptime_start': None,
    'checkpoint_due': None
}

class FlaskAsyncHelper:
    """Helper class to run async operations in Flask routes."""
    
    def __init__(self):
        self.loop = None
        self.thread = None
    
    def start_loop(self):
        """Start the asyncio event loop in a separate thread."""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
        
        # Wait for loop to be ready
        while self.loop is None:
            time.sleep(0.1)
    
    def run_async(self, coro):
        """Run an async coroutine from a sync context."""
        if self.loop is None:
            self.start_loop()
        
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=30)  # 30 second timeout

async_helper = FlaskAsyncHelper()

@app.route('/')
def dashboard():
    """Main dashboard page."""
    try:
        # Get current status
        worker_status = task_executor.get_worker_status()
        queue_stats = async_helper.run_async(task_executor.get_queue_status())
        model_status = model_handler.get_handler_status()
        git_stats = git_manager.get_repository_stats()
        
        return render_template('index.html', 
                             worker_status=worker_status,
                             queue_stats=queue_stats,
                             model_status=model_status,
                             git_stats=git_stats,
                             agent_state=agent_state)
    
    except Exception as e:
        db_logger.logger.error(f"Dashboard error: {e}")
        return render_template('index.html', 
                             error=f"Dashboard error: {e}",
                             agent_state=agent_state)

@app.route('/logs')
def logs_page():
    """Logs viewing page."""
    return render_template('logs.html')

@app.route('/settings')
def settings_page():
    """Settings configuration page."""
    current_settings = {
        'model_type': config.MODEL_TYPE,
        'model_name': config.MODEL_NAME,
        'worker_count': config.WORKER_COUNT,
        'max_retries': config.MAX_RETRIES,
        'task_timeout': config.TASK_TIMEOUT,
        'git_auto_push': config.GIT_AUTO_PUSH
    }
    
    model_status = model_handler.get_handler_status()
    
    return render_template('settings.html', 
                         current_settings=current_settings,
                         model_status=model_status)

# API Routes

@app.route('/api/status')
def api_status():
    """Get current system status."""
    try:
        worker_status = task_executor.get_worker_status()
        queue_stats = async_helper.run_async(task_executor.get_queue_status())
        model_status = model_handler.get_handler_status()
        git_stats = git_manager.get_repository_stats()
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'agent_state': agent_state,
            'workers': worker_status,
            'queue': queue_stats,
            'models': model_status,
            'git': git_stats
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/logs')
def api_logs():
    """Get recent logs."""
    try:
        limit = request.args.get('limit', 100, type=int)
        logs = db_logger.get_recent_logs(limit)
        
        return jsonify({
            'success': True,
            'logs': logs
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/logs/stream')
def api_logs_stream():
    """Stream logs in real-time using Server-Sent Events."""
    def generate_logs():
        last_log_id = 0
        while True:
            try:
                # Get recent logs
                logs = db_logger.get_recent_logs(50)
                
                # Send new logs
                for log in logs:
                    if log['id'] > last_log_id:
                        data = json.dumps(log)
                        yield f"data: {data}\n\n"
                        last_log_id = log['id']
                
                time.sleep(2)  # Poll every 2 seconds
                
            except Exception as e:
                error_data = json.dumps({'error': str(e)})
                yield f"data: {error_data}\n\n"
                time.sleep(5)
    
    return Response(generate_logs(), mimetype='text/plain')

@app.route('/api/task', methods=['POST'])
def api_add_task():
    """Add a new task to the queue."""
    try:
        data = request.get_json()
        
        if not data:
            # Try to get text data
            text_data = request.get_data(as_text=True)
            if text_data:
                task_id = async_helper.run_async(
                    task_executor.add_task_from_text(text_data)
                )
            else:
                return jsonify({
                    'success': False,
                    'error': 'No task data provided'
                }), 400
        else:
            # JSON data
            task_id = async_helper.run_async(
                task_executor.add_task_from_json(data)
            )
        
        if task_id:
            return jsonify({
                'success': True,
                'task_id': task_id,
                'message': 'Task added to queue'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to add task to queue'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/pause', methods=['POST'])
def api_pause():
    """Pause/resume the agent."""
    try:
        action = request.json.get('action', 'toggle') if request.json else 'toggle'
        
        if action == 'pause' or (action == 'toggle' and not agent_state['is_paused']):
            async_helper.run_async(task_executor.pause_workers())
            agent_state['is_paused'] = True
            message = 'Agent paused'
        
        elif action == 'resume' or (action == 'toggle' and agent_state['is_paused']):
            async_helper.run_async(task_executor.resume_workers())
            agent_state['is_paused'] = False
            message = 'Agent resumed'
        
        else:
            message = 'No action taken'
        
        return jsonify({
            'success': True,
            'is_paused': agent_state['is_paused'],
            'message': message
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/restart-worker', methods=['POST'])
def api_restart_worker():
    """Restart a specific worker."""
    try:
        worker_id = request.json.get('worker_id') if request.json else None
        
        if not worker_id:
            return jsonify({
                'success': False,
                'error': 'Worker ID required'
            }), 400
        
        success = async_helper.run_async(task_executor.restart_worker(worker_id))
        
        return jsonify({
            'success': success,
            'message': f'Worker {worker_id} {"restarted" if success else "restart failed"}'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/settings', methods=['POST'])
def api_update_settings():
    """Update system settings."""
    try:
        settings = request.json
        
        if not settings:
            return jsonify({
                'success': False,
                'error': 'No settings provided'
            }), 400
        
        # Update model settings
        if 'model_type' in settings:
            if model_handler.switch_handler(settings['model_type']):
                config.MODEL_TYPE = settings['model_type']
            else:
                return jsonify({
                    'success': False,
                    'error': f'Model type {settings["model_type"]} not available'
                }), 400
        
        # Note: Other settings would require system restart to take effect
        # This is a simplified implementation
        
        return jsonify({
            'success': True,
            'message': 'Settings updated (some changes require restart)'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/git/commits')
def api_git_commits():
    """Get recent git commits."""
    try:
        limit = request.args.get('limit', 10, type=int)
        commits = git_manager.get_recent_commits(limit)
        
        return jsonify({
            'success': True,
            'commits': commits
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def start_flask_server():
    """Start the Flask server."""
    db_logger.logger.info(f"Starting Flask server on {config.FLASK_HOST}:{config.FLASK_PORT}")
    
    # Initialize async helper
    async_helper.start_loop()
    
    # Start Flask app
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        threaded=True
    )

if __name__ == '__main__':
    start_flask_server() 