import subprocess
import requests
import json
import time
import os
from typing import Optional, Dict, Any, Tuple
from abc import ABC, abstractmethod
from config import config
from logger import db_logger

class BaseModelHandler(ABC):
    """Abstract base class for model handlers."""
    
    @abstractmethod
    async def generate_code(self, prompt: str, task_id: str) -> Tuple[str, Dict[str, Any]]:
        """Generate code based on the prompt."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the model is available."""
        pass

class OllamaHandler(BaseModelHandler):
    """Handler for Ollama models."""
    
    def __init__(self, base_url: str = None, model_name: str = None):
        self.base_url = base_url or config.OLLAMA_BASE_URL
        self.model_name = model_name or config.MODEL_NAME
        self.api_url = f"{self.base_url}/api/generate"
    
    def is_available(self) -> bool:
        """Check if Ollama server is running and model is available."""
        try:
            # Check if server is running
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                return False
            
            # Check if our model is available
            models = response.json().get('models', [])
            model_names = [model.get('name', '') for model in models]
            return any(self.model_name in name for name in model_names)
            
        except Exception as e:
            db_logger.logger.error(f"Ollama availability check failed: {e}")
            return False
    
    async def generate_code(self, prompt: str, task_id: str) -> Tuple[str, Dict[str, Any]]:
        """Generate code using Ollama."""
        start_time = time.time()
        
        # Create a comprehensive coding prompt
        coding_prompt = f"""You are an autonomous coding agent. Your task is to write clean, working Python code based on the following requirement:

{prompt}

Guidelines:
1. Write complete, executable Python code
2. Include proper error handling
3. Add clear comments and docstrings
4. Follow PEP 8 style guidelines
5. Include necessary imports
6. If creating tests, use pytest

Provide ONLY the code without explanations. The code should be ready to run.

Code:"""

        try:
            payload = {
                "model": self.model_name,
                "prompt": coding_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Lower temperature for more consistent code
                    "num_predict": 2048,
                    "top_p": 0.9
                }
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=config.TASK_TIMEOUT,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            result = response.json()
            
            response_time = time.time() - start_time
            generated_code = result.get('response', '').strip()
            
            # Extract stats
            stats = {
                'model_type': 'ollama',
                'model_name': self.model_name,
                'prompt_tokens': len(coding_prompt.split()),  # Rough estimation
                'completion_tokens': len(generated_code.split()),  # Rough estimation
                'response_time': response_time,
                'success': True
            }
            
            # Log model usage
            db_logger.log_model_stats(
                task_id, 'ollama', self.model_name,
                stats['prompt_tokens'], stats['completion_tokens'], response_time
            )
            
            return generated_code, stats
            
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = f"Ollama generation failed: {e}"
            db_logger.logger.error(error_msg)
            
            stats = {
                'model_type': 'ollama',
                'model_name': self.model_name,
                'prompt_tokens': len(coding_prompt.split()),
                'completion_tokens': 0,
                'response_time': response_time,
                'success': False,
                'error': str(e)
            }
            
            return "", stats

class OpenAIHandler(BaseModelHandler):
    """Handler for OpenAI models."""
    
    def __init__(self, api_key: str = None, model_name: str = "gpt-3.5-turbo"):
        self.api_key = api_key or config.OPENAI_API_KEY
        self.model_name = model_name
        self.api_url = "https://api.openai.com/v1/chat/completions"
    
    def is_available(self) -> bool:
        """Check if OpenAI API key is available."""
        return self.api_key is not None and self.api_key != "your_openai_api_key_here"
    
    async def generate_code(self, prompt: str, task_id: str) -> Tuple[str, Dict[str, Any]]:
        """Generate code using OpenAI."""
        if not self.is_available():
            return "", {'success': False, 'error': 'OpenAI API key not configured'}
        
        start_time = time.time()
        
        try:
            import openai
            
            # Set API key
            openai.api_key = self.api_key
            
            system_prompt = """You are an autonomous coding agent. Write clean, working Python code based on user requirements. 
            
Guidelines:
- Write complete, executable Python code
- Include proper error handling
- Add clear comments and docstrings
- Follow PEP 8 style guidelines
- Include necessary imports
- If creating tests, use pytest

Provide ONLY the code without explanations."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            response = openai.ChatCompletion.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
                max_tokens=2048
            )
            
            response_time = time.time() - start_time
            generated_code = response.choices[0].message.content.strip()
            
            # Extract stats
            usage = response.get('usage', {})
            stats = {
                'model_type': 'openai',
                'model_name': self.model_name,
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0),
                'response_time': response_time,
                'success': True
            }
            
            # Log model usage
            db_logger.log_model_stats(
                task_id, 'openai', self.model_name,
                stats['prompt_tokens'], stats['completion_tokens'], response_time
            )
            
            return generated_code, stats
            
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = f"OpenAI generation failed: {e}"
            db_logger.logger.error(error_msg)
            
            stats = {
                'model_type': 'openai',
                'model_name': self.model_name,
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'response_time': response_time,
                'success': False,
                'error': str(e)
            }
            
            return "", stats

class GPT4AllHandler(BaseModelHandler):
    """Handler for GPT4All models."""
    
    def __init__(self, model_path: str = None):
        self.model_path = model_path or config.GPT4ALL_MODEL_PATH
    
    def is_available(self) -> bool:
        """Check if GPT4All model file exists."""
        return os.path.exists(self.model_path)
    
    async def generate_code(self, prompt: str, task_id: str) -> Tuple[str, Dict[str, Any]]:
        """Generate code using GPT4All."""
        if not self.is_available():
            return "", {'success': False, 'error': 'GPT4All model file not found'}
        
        start_time = time.time()
        
        try:
            # This is a placeholder - GPT4All would need proper integration
            # You would need to install and configure GPT4All properly
            
            coding_prompt = f"""You are an autonomous coding agent. Write clean, working Python code for: {prompt}

Provide ONLY the code without explanations."""

            # Simulate GPT4All call (replace with actual implementation)
            generated_code = f"""# TODO: Implement GPT4All integration
# Task: {prompt}
print("GPT4All handler needs implementation")
"""
            
            response_time = time.time() - start_time
            
            stats = {
                'model_type': 'gpt4all',
                'model_name': os.path.basename(self.model_path),
                'prompt_tokens': len(coding_prompt.split()),
                'completion_tokens': len(generated_code.split()),
                'response_time': response_time,
                'success': True
            }
            
            # Log model usage
            db_logger.log_model_stats(
                task_id, 'gpt4all', os.path.basename(self.model_path),
                stats['prompt_tokens'], stats['completion_tokens'], response_time
            )
            
            return generated_code, stats
            
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = f"GPT4All generation failed: {e}"
            db_logger.logger.error(error_msg)
            
            stats = {
                'model_type': 'gpt4all',
                'model_name': os.path.basename(self.model_path),
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'response_time': response_time,
                'success': False,
                'error': str(e)
            }
            
            return "", stats

class ModelHandler:
    """Main model handler that manages different AI model backends."""
    
    def __init__(self):
        self.handlers = {
            'ollama': OllamaHandler(),
            'openai': OpenAIHandler(),
            'gpt4all': GPT4AllHandler()
        }
        self.current_handler = None
        self._initialize_handler()
    
    def _initialize_handler(self):
        """Initialize the current handler based on config."""
        preferred_type = config.MODEL_TYPE.lower()
        
        # Try preferred handler first
        if preferred_type in self.handlers:
            handler = self.handlers[preferred_type]
            if handler.is_available():
                self.current_handler = handler
                db_logger.logger.info(f"Initialized {preferred_type} model handler")
                return
        
        # Fallback to any available handler
        for handler_type, handler in self.handlers.items():
            if handler.is_available():
                self.current_handler = handler
                db_logger.logger.warning(f"Preferred model {preferred_type} not available, using {handler_type}")
                return
        
        # No handlers available
        db_logger.logger.error("No model handlers available!")
        self.current_handler = None
    
    def is_available(self) -> bool:
        """Check if any model handler is available."""
        return self.current_handler is not None
    
    async def generate_code(self, prompt: str, task_id: str) -> Tuple[str, Dict[str, Any]]:
        """Generate code using the current handler."""
        if not self.current_handler:
            error_msg = "No model handler available"
            db_logger.log_event(task_id, 'MODEL_HANDLER', 'MODEL_HANDLER', 'ERROR', error_msg)
            return "", {'success': False, 'error': error_msg}
        
        try:
            db_logger.log_event(task_id, 'MODEL_HANDLER', 'MODEL_HANDLER', 'INFO', 
                              f'Generating code with {type(self.current_handler).__name__}')
            
            code, stats = await self.current_handler.generate_code(prompt, task_id)
            
            if stats.get('success', False):
                db_logger.log_event(task_id, 'MODEL_HANDLER', 'MODEL_HANDLER', 'INFO', 
                                  f'Code generation successful: {len(code)} characters')
            else:
                db_logger.log_event(task_id, 'MODEL_HANDLER', 'MODEL_HANDLER', 'ERROR', 
                                  f'Code generation failed: {stats.get("error", "Unknown error")}')
            
            return code, stats
            
        except Exception as e:
            error_msg = f"Model handler error: {e}"
            db_logger.log_event(task_id, 'MODEL_HANDLER', 'MODEL_HANDLER', 'ERROR', error_msg)
            return "", {'success': False, 'error': error_msg}
    
    def get_handler_status(self) -> Dict[str, Any]:
        """Get status of all handlers."""
        status = {}
        for handler_type, handler in self.handlers.items():
            status[handler_type] = {
                'available': handler.is_available(),
                'current': handler == self.current_handler
            }
        return status
    
    def switch_handler(self, handler_type: str) -> bool:
        """Switch to a different handler."""
        if handler_type not in self.handlers:
            return False
        
        handler = self.handlers[handler_type]
        if not handler.is_available():
            return False
        
        self.current_handler = handler
        db_logger.logger.info(f"Switched to {handler_type} model handler")
        return True

# Global model handler instance
model_handler = ModelHandler() 