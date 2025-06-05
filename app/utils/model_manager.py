"""
Model availability verification and management utilities
"""

import requests
import time
from typing import List, Dict, Optional
from flask import current_app


class ModelManager:
    """Manages Ollama model availability and verification"""
    
    def __init__(self, ollama_host: str = None):
        self.ollama_host = ollama_host or current_app.config.get('OLLAMA_HOST', 'http://localhost:11434')
        self.required_models = [
            'qwen3-summarizer:14b',
            'qwen3-summarizer:30b'
        ]
    
    def check_ollama_health(self, timeout: int = 5) -> bool:
        """Check if Ollama service is responding"""
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            current_app.logger.warning(f"Ollama health check failed: {e}")
            return False
    
    def get_available_models(self) -> List[str]:
        """Get list of available models from Ollama"""
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except Exception as e:
            current_app.logger.error(f"Failed to get available models: {e}")
            return []
    
    def check_model_availability(self) -> Dict[str, bool]:
        """Check availability of all required models"""
        available_models = self.get_available_models()
        return {
            model: model in available_models 
            for model in self.required_models
        }
    
    def get_model_status(self) -> Dict[str, any]:
        """Get comprehensive model status information"""
        status = {
            'ollama_healthy': self.check_ollama_health(),
            'models': {},
            'all_models_ready': False,
            'available_models': []
        }
        
        if status['ollama_healthy']:
            status['available_models'] = self.get_available_models()
            model_availability = self.check_model_availability()
            status['models'] = model_availability
            status['all_models_ready'] = all(model_availability.values())
        
        return status
    
    def wait_for_models(self, max_wait_seconds: int = 300, check_interval: int = 30) -> bool:
        """
        Wait for all required models to become available
        
        Args:
            max_wait_seconds: Maximum time to wait in seconds
            check_interval: How often to check in seconds
            
        Returns:
            True if all models are available, False if timeout
        """
        start_time = time.time()
        
        current_app.logger.info(f"Waiting for required models: {', '.join(self.required_models)}")
        
        while time.time() - start_time < max_wait_seconds:
            status = self.get_model_status()
            
            if status['all_models_ready']:
                current_app.logger.info("All required models are available")
                return True
            
            missing_models = [
                model for model, available in status['models'].items() 
                if not available
            ]
            
            current_app.logger.info(
                f"Waiting for models: {', '.join(missing_models)}. "
                f"Checking again in {check_interval} seconds..."
            )
            
            time.sleep(check_interval)
        
        current_app.logger.warning(f"Timeout waiting for models after {max_wait_seconds} seconds")
        return False
    
    def get_default_model(self, prefer_smaller: bool = True) -> Optional[str]:
        """
        Get the best available model for summarization
        
        Args:
            prefer_smaller: If True, prefer 14b model over 30b for faster processing
            
        Returns:
            Model name or None if no models available
        """
        status = self.get_model_status()
        
        if not status['ollama_healthy']:
            return None
        
        # Define preference order
        if prefer_smaller:
            preference_order = ['qwen3-summarizer:14b', 'qwen3-summarizer:30b']
        else:
            preference_order = ['qwen3-summarizer:30b', 'qwen3-summarizer:14b']
        
        for model in preference_order:
            if status['models'].get(model, False):
                return model
        
        return None
    
    def validate_model_response(self, model_name: str, timeout: int = 30) -> bool:
        """
        Test if a model can generate responses
        
        Args:
            model_name: Name of the model to test
            timeout: Request timeout in seconds
            
        Returns:
            True if model responds correctly, False otherwise
        """
        test_prompt = "Please respond with exactly: 'Model test successful'"
        
        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": model_name,
                    "prompt": test_prompt,
                    "stream": False
                },
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                response_text = data.get('response', '').strip()
                return 'Model test successful' in response_text
            
            return False
            
        except Exception as e:
            current_app.logger.error(f"Model validation failed for {model_name}: {e}")
            return False


def verify_models_on_startup(app, max_wait_seconds: int = 180) -> bool:
    """
    Verify model availability during app startup
    
    Args:
        app: Flask application instance
        max_wait_seconds: Maximum time to wait for models
        
    Returns:
        True if models are ready, False otherwise
    """
    with app.app_context():
        manager = ModelManager()
        
        app.logger.info("Verifying Ollama model availability...")
        
        # Quick health check first
        if not manager.check_ollama_health():
            app.logger.warning("Ollama service is not responding. Models will not be available.")
            return False
        
        # Check if models are immediately available
        status = manager.get_model_status()
        if status['all_models_ready']:
            app.logger.info("All required models are immediately available")
            return True
        
        # Wait for models to become available
        app.logger.info("Some models are missing. Waiting for initialization to complete...")
        
        if manager.wait_for_models(max_wait_seconds):
            app.logger.info("Model verification successful")
            return True
        else:
            app.logger.warning("Model verification timed out. Some features may not work correctly.")
            return False


# Global model manager instance
model_manager = ModelManager()