# src/services/llm_client.py
"""
LLM Client for title optimization
"""

import os
import time
from typing import Optional, Dict, Any
import logging

class LLMClient:
    """Client for interacting with LLM APIs"""
    
    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo", **kwargs):
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = kwargs.get('max_tokens', 500)
        self.temperature = kwargs.get('temperature', 0.7)
        self.logger = logging.getLogger(__name__)
        
        # Initialize the appropriate client based on model
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the LLM client based on the model"""
        try:
            if "gpt" in self.model_name.lower():
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                self.client_type = "openai"
            elif "claude" in self.model_name.lower():
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                self.client_type = "anthropic"
            else:
                raise ValueError(f"Unsupported model: {self.model_name}")
                
            self.logger.info(f"Initialized {self.client_type} client with model: {self.model_name}")
            
        except ImportError as e:
            self.logger.error(f"Failed to import required library: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM client: {e}")
            raise
    
    def generate_response(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Generate response from LLM"""
        start_time = time.time()
        
        try:
            if self.client_type == "openai":
                response = self._call_openai(prompt, max_tokens)
            elif self.client_type == "anthropic":
                response = self._call_anthropic(prompt, max_tokens)
            else:
                raise ValueError(f"Unsupported client type: {self.client_type}")
            
            processing_time = time.time() - start_time
            self.logger.info(f"LLM response generated in {processing_time:.2f} seconds")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating LLM response: {e}")
            raise
    
    def _call_openai(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Call OpenAI API"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert Amazon product title optimizer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens or self.max_tokens,
                temperature=self.temperature
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise
    
    def _call_anthropic(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Call Anthropic API"""
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens or self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text.strip()
            
        except Exception as e:
            self.logger.error(f"Anthropic API error: {e}")
            raise
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            'model_name': self.model_name,
            'client_type': self.client_type,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'api_key_set': bool(self.api_key)
        }
