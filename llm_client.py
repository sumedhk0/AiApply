"""
LLM Client Wrapper for OpenRouter API
Provides a unified interface for OpenRouter models (MiMo v2 Flash).
"""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    """
    Wrapper class for OpenRouter API using OpenAI SDK format.
    """

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not set. "
                "Please set it in your .env file."
            )

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key
        )
        self.model = "xiaomi/mimo-v2-flash:free"

    def create_message(self, prompt, max_tokens=4096, system_prompt=None):
        """
        Create a message using OpenRouter API.

        Args:
            prompt: User prompt (string or list of content blocks)
            max_tokens: Maximum tokens to generate
            system_prompt: Optional system prompt

        Returns:
            str: The model's response text
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Handle string prompt or content list
        if isinstance(prompt, str):
            messages.append({"role": "user", "content": prompt})
        elif isinstance(prompt, list):
            # Convert content blocks to text-only format
            content_str = self._convert_content_blocks(prompt)
            messages.append({"role": "user", "content": content_str})

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages
        )

        return response.choices[0].message.content

    def _convert_content_blocks(self, content_blocks):
        """
        Convert content blocks to text-only format.
        OpenRouter/MiMo doesn't support document attachments.
        """
        text_parts = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)


# Singleton instance for global use
_client = None


def get_client(api_key=None):
    """Get or create the LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient(api_key)
    return _client


def reset_client():
    """Reset the singleton client (useful for testing)."""
    global _client
    _client = None
