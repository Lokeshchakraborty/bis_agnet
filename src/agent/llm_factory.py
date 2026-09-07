"""
Unified LLM Factory for Multi-Provider & BYOK Execution
=========================================================
Supports Google Gemini, Mistral AI, OpenAI, OpenRouter, and Ollama (Local).
"""
from __future__ import annotations

import logging
import os
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from src.config import CONFIG

logger = logging.getLogger("bis_llm_factory")


def create_llm_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.2,
) -> BaseChatModel:
    """
    Instantiate the appropriate LangChain ChatModel based on provider and model parameters.
    """
    prov = (provider or os.getenv("LLM_PROVIDER") or "google").lower().strip()
    mod = (model_name or os.getenv("LLM_MODEL") or CONFIG.llm_model or "gemini-3.5-flash").strip()

    logger.info("Initializing LLM -> Provider: '%s', Model: '%s', BaseURL: '%s'", prov, mod, base_url or "default")

    # 1. Ollama (Local LLM - NO API Key Required)
    if prov in ("ollama", "local_ollama", "ollama_local") or "ollama" in mod.lower() or mod in ("llama3.2", "llama3.1", "mistral", "qwen2.5", "phi4", "gemma2", "deepseek-r1:8b", "llama2", "gemma"):
        from langchain_ollama import ChatOllama
        url = base_url or os.getenv("OLLAMA_BASE_URL") or CONFIG.ollama_base_url or "http://localhost:11434"
        logger.info("Initializing ChatOllama [model: '%s', base_url: '%s']", mod, url)
        return ChatOllama(
            model=mod,
            base_url=url,
            temperature=temperature,
        )

    # 2. Mistral AI
    elif prov in ("mistral", "mistralai") or "mistral" in mod.lower() or "codestral" in mod.lower() or "mixtral" in mod.lower():
        from langchain_mistralai import ChatMistralAI
        key = api_key or os.getenv("MISTRAL_API_KEY") or CONFIG.mistral_api_key
        logger.info("Initializing ChatMistralAI [model: '%s']", mod)
        return ChatMistralAI(
            model=mod,
            api_key=key,
            temperature=temperature,
        )

    # 3. OpenAI API
    elif prov == "openai" or mod.startswith("gpt-") or mod.startswith("o1") or mod.startswith("o3"):
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("OPENAI_API_KEY")
        url = base_url or os.getenv("OPENAI_BASE_URL")
        kwargs = {"model": mod, "api_key": key, "temperature": temperature}
        if url:
            kwargs["base_url"] = url
        logger.info("Initializing ChatOpenAI [model: '%s']", mod)
        return ChatOpenAI(**kwargs)

    # 4. OpenRouter API
    elif prov == "openrouter" or "/" in mod:
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("OPENROUTER_API_KEY")
        url = base_url or "https://openrouter.ai/api/v1"
        logger.info("Initializing OpenRouter ChatOpenAI [model: '%s']", mod)
        return ChatOpenAI(
            model=mod,
            api_key=key,
            base_url=url,
            temperature=temperature,
        )

    # 5. Default Google Gemini API
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        # Strip any leading models/ prefix
        if mod.startswith("models/"):
            mod = mod[len("models/"):]

        # Deprecation compatibility table: automatically remap retired models
        LEGACY_GEMINI_REMAP = {
            "gemini-2.5-flash": "gemini-3.5-flash",
            "gemini-2.5-flash-lite": "gemini-3.5-flash-lite",
            "gemini-2.5-pro": "gemini-pro-latest",
            "gemini-2.0-flash": "gemini-3.5-flash",
            "gemini-2.0-flash-exp": "gemini-3.5-flash",
            "gemini-2.0-pro-exp": "gemini-pro-latest",
            "gemini-1.5-flash": "gemini-3.5-flash",
            "gemini-1.5-flash-8b": "gemini-3.5-flash-lite",
            "gemini-1.5-pro": "gemini-pro-latest",
            "gemini-1.0-pro": "gemini-3.5-flash",
        }
        if mod in LEGACY_GEMINI_REMAP:
            target_mod = LEGACY_GEMINI_REMAP[mod]
            logger.warning(
                "Deprecated Gemini model '%s' requested. Transparently auto-migrating to '%s' to prevent 404 NOT_FOUND.",
                mod,
                target_mod,
            )
            mod = target_mod

        logger.info("Initializing ChatGoogleGenerativeAI [model: '%s']", mod)
        kwargs = {"model": mod, "temperature": temperature}
        if key:
            kwargs["google_api_key"] = key
        return ChatGoogleGenerativeAI(**kwargs)
