from typing import Optional, Any, Type, List
from dataclasses import dataclass
import os
import logging
from openai import OpenAI
from groq import Groq
import google.generativeai as genai
import json
import re

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    
    def __post_init__(self):
        """Load from environment if not provided."""
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.groq_api_key:
            self.groq_api_key = os.getenv("GROQ_API_KEY")
        if not self.gemini_api_key:
            self.gemini_api_key = os.getenv("GEMINI_API_KEY")


class LLMRouter:
    """
    Route LLM requests to multiple providers with fallback chain.
    
    Fallback chain: OpenAI → Groq → Gemini
    """
    
    def __init__(self, config: LLMConfig):
        """
        Initialize router with provider configs.
        
        Args:
            config: LLMConfig with API keys
        """
        self.config = config
        self.openai_client = None
        self.groq_client = None
        self.gemini_client = None
        
        # Initialize available clients
        self._init_clients()
    
    def _init_clients(self):
        """Initialize LLM clients based on available keys."""
        try:
            if self.config.openai_api_key:
                
                self.openai_client = OpenAI(api_key=self.config.openai_api_key)
                logger.info("[LLMRouter] OpenAI client initialized")
        except Exception as e:
            logger.warning(f"[LLMRouter] OpenAI initialization failed: {e}")
        
        try:
            if self.config.groq_api_key:
                
                self.groq_client = Groq(api_key=self.config.groq_api_key)
                logger.info("[LLMRouter] Groq client initialized")
        except Exception as e:
            logger.warning(f"[LLMRouter] Groq initialization failed: {e}")
        
        try:
            if self.config.gemini_api_key:
                
                genai.configure(api_key=self.config.gemini_api_key)
                self.gemini_client = genai
                logger.info("[LLMRouter] Gemini client initialized")
        except Exception as e:
            logger.warning(f"[LLMRouter] Gemini initialization failed: {e}")
    
    def invoke(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model: str = "auto"
    ) -> str:
        """
        Route request through fallback chain.
        
        Args:
            messages: List of message dicts with role and content
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum output tokens
            model: "auto" or specific model name
        
        Returns:
            Response text from first successful provider
        """
        # Try OpenAI first
        if self.openai_client:
            try:
                logger.debug("[LLMRouter] Attempting OpenAI...")
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o" if model == "auto" else model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                logger.info("[LLMRouter] Request successful via OpenAI")
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"[LLMRouter] OpenAI failed: {e}, trying Groq...")
        
        # Try Groq
        if self.groq_client:
            try:
                logger.debug("[LLMRouter] Attempting Groq...")
                response = self.groq_client.chat.completions.create(
                    model="mixtral-8x7b-32768" if model == "auto" else model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                logger.info("[LLMRouter] Request successful via Groq")
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"[LLMRouter] Groq failed: {e}, trying Gemini...")
        
        # Try Gemini
        if self.gemini_client:
            try:
                logger.debug("[LLMRouter] Attempting Gemini...")
                model_name = "gemini-2.5-flash" if model == "auto" else model
                model_obj = self.gemini_client.GenerativeModel(model_name)
                
                # Convert messages to Gemini format
                gemini_messages = []
                for msg in messages:
                    role = "user" if msg["role"] == "user" else "model"
                    gemini_messages.append({"role": role, "parts": msg["content"]})
                
                response = model_obj.generate_content(gemini_messages)
                logger.info("[LLMRouter] Request successful via Gemini")
                return response.text
            except Exception as e:
                logger.warning(f"[LLMRouter] Gemini failed: {e}")
        
        # All providers failed
        raise RuntimeError(
            "All LLM providers failed. Please check API keys and credentials."
        )
    
    def structured_output(
        self,
        messages: List[dict],
        response_model: Type[Any],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        model: str = "auto"
    ) -> Any:
        """
        Route request with structured output (JSON) validation.
        
        Args:
            messages: List of message dicts
            response_model: Pydantic model for output validation
            system_prompt: System message to prepend
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            model: "auto" or specific model name
        
        Returns:
            Instance of response_model with validated data
        """
        # Try OpenAI with structured output (GPT-4 Turbo supports this)
        if self.openai_client:
            try:
                logger.debug("[LLMRouter] Attempting OpenAI with structured output...")
                
                # Build system message
                all_messages = []
                if system_prompt:
                    all_messages.append({"role": "system", "content": system_prompt})
                all_messages.extend(messages)
                
                # Use JSON mode for structured output
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o" if model == "auto" else model,
                    messages=all_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"}
                )
                
                # Parse and validate
                import json
                response_text = response.choices[0].message.content
                response_data = json.loads(response_text)
                
                logger.info("[LLMRouter] Structured output successful via OpenAI")
                return response_model(**response_data)
            except Exception as e:
                logger.warning(f"[LLMRouter] OpenAI structured output failed: {e}")
        
        # Fallback: regular invoke + Pydantic validation
        logger.debug("[LLMRouter] Falling back to standard invoke + validation...")
        
        prompt = f"""
{system_prompt}

Return ONLY valid JSON matching this schema:
{response_model.model_json_schema()}

User request:
{messages[-1]['content']}
"""
        
        response_text = self.invoke(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            model=model
        )
        
        # Try to extract JSON from response
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                response_data = json.loads(json_str)
                return response_model(**response_data)
        except json.JSONDecodeError:
            pass
        
        # If parsing fails, raise error
        raise ValueError(
            f"Failed to parse structured output from LLM. Response: {response_text[:200]}"
        )
