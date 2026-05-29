"""
LLM service for Ollama integration.
Connects to locally running Ollama with Llama 3.1 8B for response generation.
Supports both streaming and non-streaming modes.
"""

import httpx
import json
import time
from typing import AsyncGenerator, Optional
from app.core.config import get_settings
from app.core.logging_config import get_logger


# System prompt that enforces grounded, non-hallucinating responses
SYSTEM_PROMPT = """You are an AI assistant for SWS AI company. Your role is to answer employee questions using ONLY the provided context from company documents.

STRICT RULES:
1. Answer ONLY using the information provided in the context below.
2. If the context does not contain enough information to answer the question, respond with: "I don't have that information in the company documents."
3. Do NOT make assumptions or use external knowledge beyond what is provided.
4. Be concise and precise in your answers.
5. When possible, cite which document the information comes from.
6. Format your response clearly using bullet points or numbered lists when appropriate.
7. If the question is ambiguous, provide the most relevant information from the context.

CONTEXT FROM COMPANY DOCUMENTS:
{context}

Answer the following question based ONLY on the above context."""


class LLMService:
    """Manages LLM interactions via Ollama REST API."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger()
        self.base_url = self.settings.ollama_base_url
        self.model = self.settings.ollama_model

    def _build_prompt(self, question: str, context: str) -> str:
        """
        Build the complete prompt with system instructions and context.

        Args:
            question: The user's question.
            context: Retrieved document context.

        Returns:
            Formatted prompt string.
        """
        system = SYSTEM_PROMPT.format(context=context)
        return f"{system}\n\nQuestion: {question}\n\nAnswer:"

    async def generate(self, question: str, context: str) -> str:
        """
        Generate a non-streaming response from Ollama.

        Args:
            question: The user's question.
            context: Retrieved document chunks as context.

        Returns:
            The generated answer string.
        """
        prompt = self._build_prompt(question, context)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 1024,
            },
        }

        self.logger.info(f"Sending request to Ollama ({self.model})")
        start = time.time()

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

            elapsed = time.time() - start
            self.logger.info(f"LLM response generated in {elapsed:.2f}s")

            return result.get("response", "").strip()

        except httpx.ConnectError:
            self.logger.error("Cannot connect to Ollama. Is it running?")
            raise ConnectionError(
                "Cannot connect to Ollama. Please ensure Ollama is running "
                f"at {self.base_url}. Start it with: ollama serve"
            )
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Ollama HTTP error: {e.response.status_code}")
            raise
        except Exception as e:
            self.logger.error(f"LLM generation error: {str(e)}")
            raise

    async def generate_stream(
        self, question: str, context: str
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from Ollama.
        Yields tokens as they are generated.

        Args:
            question: The user's question.
            context: Retrieved document chunks as context.

        Yields:
            Individual tokens/text chunks as they are generated.
        """
        prompt = self._build_prompt(question, context)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": 0.0,
                "num_predict": 1024,
            },
        }

        self.logger.info(f"Starting streaming request to Ollama ({self.model})")
        start = time.time()

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("response", "")
                                if token:
                                    yield token

                                # Check if generation is complete
                                if data.get("done", False):
                                    elapsed = time.time() - start
                                    self.logger.info(
                                        f"Streaming complete in {elapsed:.2f}s"
                                    )
                                    break
                            except json.JSONDecodeError:
                                continue

        except httpx.ConnectError:
            self.logger.error("Cannot connect to Ollama. Is it running?")
            yield "Error: Cannot connect to Ollama. Please ensure Ollama is running."
        except Exception as e:
            self.logger.error(f"Streaming error: {str(e)}")
            yield f"Error: {str(e)}"

    async def check_health(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    # Check if our model is available (with or without :latest tag)
                    for name in model_names:
                        if self.model in name or name in self.model:
                            return True
                    self.logger.warning(
                        f"Model '{self.model}' not found. "
                        f"Available: {model_names}"
                    )
                    return False
        except Exception as e:
            self.logger.error(f"Ollama health check failed: {str(e)}")
            return False
