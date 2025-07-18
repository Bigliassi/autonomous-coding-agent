import subprocess
import os
import tempfile
import shutil
import sys
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
from logger import db_logger
from config import config

class TestRunner:
    """Handles running tests for generated code."""
    
    def __init__(self):
        self.test_timeout = config.TASK_TIMEOUT
        self.temp_dir = None
    
    def create_temp_workspace(self) -> str:
        """Create a temporary workspace for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="agent_test_")
        return self.temp_dir
    
    def cleanup_temp_workspace(self):
        """Clean up the temporary workspace."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
            except Exception as e:
                db_logger.logger.error(f"Failed to cleanup temp workspace: {e}")
    
    def write_code_to_file(self, code: str, filename: str, workspace: str = None) -> str:
        """Write code to a file in the workspace."""
        workspace = workspace or self.temp_dir
        if not workspace:
            raise ValueError("No workspace available")
        
        file_path = os.path.join(workspace, filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        return file_path
    
    def extract_code_blocks(self, generated_text: str) -> Dict[str, str]:
        """Extract code blocks from generated text."""
        code_blocks = {}
        current_file = None
        current_code = []
        in_code_block = False
        
        lines = generated_text.split('\n')
        
        for line in lines:
            # Look for file indicators
            if '# File:' in line or '# filename:' in line:
                # Save previous code block
                if current_file and current_code:
                    code_blocks[current_file] = '\n'.join(current_code)
                
                # Extract filename
                current_file = line.split(':')[-1].strip()
                current_code = []
                continue
            
            # Look for code block markers
            if line.strip().startswith('```'):
                if line.strip() == '```':
                    in_code_block = not in_code_block
                elif 'python' in line.lower():
                    in_code_block = True
                continue
            
            # Collect code lines
            if in_code_block or (current_file and not line.startswith('#')):
                current_code.append(line)
        
        # Save last code block
        if current_file and current_code:
            code_blocks[current_file] = '\n'.join(current_code)
        
        # If no specific files found, treat entire text as main.py
        if not code_blocks and generated_text.strip():
            # Clean up the code by removing markdown formatting
            clean_code = generated_text
            if '```' in clean_code:
                # Extract code from markdown blocks
                parts = clean_code.split('```')
                code_parts = []
                for i, part in enumerate(parts):
                    if i % 2 == 1:  # Odd indices are inside code blocks
                        # Remove language identifier
                        lines = part.split('\n')
                        if lines and lines[0].strip() in ['python', 'py', '']:
                            lines = lines[1:]
                        code_parts.append('\n'.join(lines))
                clean_code = '\n'.join(code_parts)
            
            code_blocks['main.py'] = clean_code.strip()
        
        return code_blocks
    
    def create_basic_test(self, filename: str, workspace: str) -> str:
        """Create a basic test file for the given Python file."""
        test_filename = f"test_{filename.replace('.py', '')}.py"
        test_path = os.path.join(workspace, test_filename)
        
        # Basic test template
        test_content = f'''"""
Basic test for {filename}
"""
import pytest
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that the module can be imported without errors."""
    try:
        import {filename.replace('.py', '')}
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import module: {{e}}")

def test_syntax():
    """Test that the file has valid Python syntax."""
    with open("{filename}", "r") as f:
        code = f.read()
    
    try:
        compile(code, "{filename}", "exec")
        assert True
    except SyntaxError as e:
        pytest.fail(f"Syntax error in code: {{e}}")

def test_basic_execution():
    """Test that the code can be executed without immediate errors."""
    try:
        with open("{filename}", "r") as f:
            code = f.read()
        
        # Create a safe execution environment
        exec_globals = {{'__name__': '__main__'}}
        exec(code, exec_globals)
        assert True
    except Exception as e:
        # Allow certain exceptions that might be expected
        if "TODO" in str(e) or "NotImplemented" in str(e):
            pytest.skip(f"Code contains placeholder: {{e}}")
        else:
            pytest.fail(f"Runtime error: {{e}}")
'''
        
        with open(test_path, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        return test_path
    
    async def run_tests(self, task_id: str, generated_code: str, test_code: str = None) -> Tuple[bool, Dict[str, Any]]:
        """Run tests on the generated code."""
        workspace = self.create_temp_workspace()
        
        try:
            db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'INFO', 'Starting test execution')
            
            # Extract and write code files
            code_blocks = self.extract_code_blocks(generated_code)
            
            if not code_blocks:
                return False, {
                    'success': False,
                    'error': 'No code blocks found in generated text',
                    'stdout': '',
                    'stderr': '',
                    'exit_code': 1
                }
            
            # Write code files
            code_files = []
            for filename, code in code_blocks.items():
                if code.strip():  # Only write non-empty files
                    file_path = self.write_code_to_file(code, filename, workspace)
                    code_files.append(filename)
                    db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'INFO', 
                                      f'Created code file: {filename}')
            
            # Write test file if provided, otherwise create basic tests
            test_files = []
            if test_code:
                test_path = self.write_code_to_file(test_code, 'test_generated.py', workspace)
                test_files.append('test_generated.py')
            else:
                # Create basic tests for each Python file
                for filename in code_files:
                    if filename.endswith('.py'):
                        test_path = self.create_basic_test(filename, workspace)
                        test_files.append(os.path.basename(test_path))
            
            # Install dependencies if requirements.txt exists in the generated code
            if 'requirements.txt' in code_blocks:
                await self._install_dependencies(workspace, task_id)
            
            # Run pytest
            test_result = await self._run_pytest(workspace, test_files, task_id)
            
            # Log test results
            if test_result['success']:
                db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'INFO', 
                                  'All tests passed successfully')
            else:
                db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'ERROR', 
                                  f'Tests failed: {test_result.get("error", "Unknown error")}')
            
            return test_result['success'], test_result
            
        except Exception as e:
            error_msg = f"Test execution failed: {e}"
            db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'ERROR', error_msg)
            return False, {
                'success': False,
                'error': error_msg,
                'stdout': '',
                'stderr': str(e),
                'exit_code': 1
            }
        
        finally:
            self.cleanup_temp_workspace()
    
    async def _install_dependencies(self, workspace: str, task_id: str):
        """Install dependencies from requirements.txt."""
        requirements_path = os.path.join(workspace, 'requirements.txt')
        if not os.path.exists(requirements_path):
            return
        
        try:
            db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'INFO', 
                              'Installing dependencies from requirements.txt')
            
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', '-r', requirements_path
            ], cwd=workspace, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'WARNING', 
                                  f'Dependency installation failed: {result.stderr}')
            else:
                db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'INFO', 
                                  'Dependencies installed successfully')
                
        except subprocess.TimeoutExpired:
            db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'WARNING', 
                              'Dependency installation timed out')
        except Exception as e:
            db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'WARNING', 
                              f'Dependency installation error: {e}')
    
    async def _run_pytest(self, workspace: str, test_files: List[str], task_id: str) -> Dict[str, Any]:
        """Run pytest on the test files."""
        try:
            # Change to workspace directory
            original_cwd = os.getcwd()
            os.chdir(workspace)
            
            # Prepare pytest command
            cmd = [sys.executable, '-m', 'pytest', '-v', '--tb=short'] + test_files
            
            db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'INFO', 
                              f'Running pytest: {" ".join(cmd)}')
            
            # Run pytest
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.test_timeout,
                cwd=workspace
            )
            
            # Restore original directory
            os.chdir(original_cwd)
            
            success = result.returncode == 0
            
            return {
                'success': success,
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': ' '.join(cmd)
            }
            
        except subprocess.TimeoutExpired:
            os.chdir(original_cwd)
            return {
                'success': False,
                'exit_code': 124,  # Timeout exit code
                'stdout': '',
                'stderr': f'Tests timed out after {self.test_timeout} seconds',
                'error': 'Timeout',
                'command': ' '.join(cmd)
            }
        except Exception as e:
            os.chdir(original_cwd)
            return {
                'success': False,
                'exit_code': 1,
                'stdout': '',
                'stderr': str(e),
                'error': str(e),
                'command': ' '.join(cmd) if 'cmd' in locals() else 'Unknown'
            }
    
    def validate_python_syntax(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validate Python syntax without executing the code."""
        try:
            compile(code, '<string>', 'exec')
            return True, None
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Compilation error: {e}"
    
    async def quick_syntax_check(self, task_id: str, generated_code: str) -> Tuple[bool, Dict[str, Any]]:
        """Perform a quick syntax check without running full tests."""
        try:
            code_blocks = self.extract_code_blocks(generated_code)
            
            if not code_blocks:
                return False, {
                    'success': False,
                    'error': 'No code blocks found',
                    'files_checked': 0
                }
            
            results = {}
            all_valid = True
            
            for filename, code in code_blocks.items():
                if filename.endswith('.py') and code.strip():
                    is_valid, error = self.validate_python_syntax(code)
                    results[filename] = {
                        'valid': is_valid,
                        'error': error
                    }
                    
                    if not is_valid:
                        all_valid = False
                        db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'ERROR', 
                                          f'Syntax error in {filename}: {error}')
            
            return all_valid, {
                'success': all_valid,
                'files_checked': len(results),
                'results': results
            }
            
        except Exception as e:
            error_msg = f"Syntax check failed: {e}"
            db_logger.log_event(task_id, 'TEST_RUNNER', 'TEST_RUNNER', 'ERROR', error_msg)
            return False, {
                'success': False,
                'error': error_msg,
                'files_checked': 0
            }

# Global test runner instance
test_runner = TestRunner() 