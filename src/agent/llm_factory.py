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
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """
    Instantiate the appropriate LangChain ChatModel based on provider and model parameters.
    """
    prov = (provider or os.getenv("LLM_PROVIDER") or "google").lower().strip()
    mod = (model_name or os.getenv("LLM_MODEL") or CONFIG.llm_model or "gemini-3.5-flash-lite").strip()

    logger.info("Initializing LLM -> Provider: '%s', Model: '%s', MaxTokens: %s, BaseURL: '%s'", prov, mod, max_tokens, base_url or "default")

    # 1. Ollama (Local LLM - NO API Key Required)
    if prov in ("ollama", "local_ollama", "ollama_local"):
        from langchain_ollama import ChatOllama
        url = base_url or os.getenv("OLLAMA_BASE_URL") or CONFIG.ollama_base_url or "http://localhost:11434"
        logger.info("Initializing ChatOllama [model: '%s', base_url: '%s']", mod, url)
        ollama_kwargs = {
            "model": mod,
            "base_url": url,
            "temperature": temperature,
        }
        if max_tokens:
            ollama_kwargs["num_predict"] = max_tokens
        return ChatOllama(**ollama_kwargs)

    # 2. Hugging Face (Inference Endpoints / Serverless API)
    elif prov in ("huggingface", "hf", "hugging_face"):
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
        url = base_url or "https://router.huggingface.co/hf-inference/v1"
        logger.info("Initializing HuggingFace ChatOpenAI [model: '%s', endpoint: '%s']", mod, url)
        kwargs = {"model": mod, "api_key": key or "hf_dummy", "base_url": url, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatOpenAI(**kwargs)

    # 3. OmniRoute API Gateway
    elif prov in ("omniroute", "omni_route"):
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("OMNIROUTE_API_KEY")
        url = base_url or "https://api.omniroute.ai/v1"
        logger.info("Initializing OmniRoute ChatOpenAI [model: '%s', endpoint: '%s']", mod, url)
        kwargs = {"model": mod, "api_key": key or "omni_dummy", "base_url": url, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatOpenAI(**kwargs)

    # 4. Anthropic Claude
    elif prov in ("claude", "anthropic"):
        try:
            from langchain_anthropic import ChatAnthropic
            key = api_key or os.getenv("ANTHROPIC_API_KEY")
            logger.info("Initializing ChatAnthropic [model: '%s']", mod)
            anthropic_kwargs = {"model_name": mod, "api_key": key, "temperature": temperature}
            if max_tokens:
                anthropic_kwargs["max_tokens"] = max_tokens
            if base_url:
                anthropic_kwargs["base_url"] = base_url
            return ChatAnthropic(**anthropic_kwargs)
        except Exception as e:
            logger.warning("Failed to load langchain_anthropic: %s. Falling back to ChatOpenAI proxy.", e)
            from langchain_openai import ChatOpenAI
            key = api_key or os.getenv("ANTHROPIC_API_KEY")
            url = base_url or "https://api.anthropic.com/v1"
            return ChatOpenAI(model=mod, api_key=key, base_url=url, temperature=temperature)

    # 5. Groq Fast Inference
    elif prov == "groq":
        try:
            from langchain_groq import ChatGroq
            key = api_key or os.getenv("GROQ_API_KEY")
            logger.info("Initializing ChatGroq [model: '%s']", mod)
            groq_kwargs = {"model_name": mod, "groq_api_key": key, "temperature": temperature}
            if max_tokens:
                groq_kwargs["max_tokens"] = max_tokens
            return ChatGroq(**groq_kwargs)
        except Exception as e:
            logger.warning("Failed to load langchain_groq: %s. Falling back to ChatOpenAI.", e)
            from langchain_openai import ChatOpenAI
            key = api_key or os.getenv("GROQ_API_KEY")
            url = base_url or "https://api.groq.com/openai/v1"
            return ChatOpenAI(model=mod, api_key=key, base_url=url, temperature=temperature)

    # 6. DeepSeek API
    elif prov == "deepseek":
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("DEEPSEEK_API_KEY")
        url = base_url or "https://api.deepseek.com"
        logger.info("Initializing DeepSeek ChatOpenAI [model: '%s']", mod)
        kwargs = {"model": mod, "api_key": key, "base_url": url, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatOpenAI(**kwargs)

    # 7. Mistral AI
    elif prov in ("mistral", "mistralai"):
        from langchain_mistralai import ChatMistralAI
        key = api_key or os.getenv("MISTRAL_API_KEY") or CONFIG.mistral_api_key
        logger.info("Initializing ChatMistralAI [model: '%s']", mod)
        mistral_kwargs = {
            "model": mod,
            "api_key": key,
            "temperature": temperature,
        }
        if max_tokens:
            mistral_kwargs["max_tokens"] = max_tokens
        return ChatMistralAI(**mistral_kwargs)

    # 8. OpenAI API
    elif prov == "openai" or mod.startswith("gpt-") or mod.startswith("o1") or mod.startswith("o3"):
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("OPENAI_API_KEY")
        url = base_url or os.getenv("OPENAI_BASE_URL")
        kwargs = {"model": mod, "api_key": key, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if url:
            kwargs["base_url"] = url
        logger.info("Initializing ChatOpenAI [model: '%s']", mod)
        return ChatOpenAI(**kwargs)

    # 9. OpenRouter Multi-LLM API
    elif prov == "openrouter":
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("OPENROUTER_API_KEY")
        url = base_url or "https://openrouter.ai/api/v1"
        kwargs = {"model": mod, "api_key": key, "base_url": url, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        logger.info("Initializing OpenRouter ChatOpenAI [model: '%s']", mod)
        return ChatOpenAI(**kwargs)

    # 10. Fallback heuristics for slash models
    elif "/" in mod and prov not in ("gemini", "google"):
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("HF_TOKEN")
        url = base_url or "https://openrouter.ai/api/v1"
        kwargs = {"model": mod, "api_key": key, "base_url": url, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatOpenAI(**kwargs)

    # 11. Google Gemini API (Default)
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        # Strip any leading models/ prefix
        if mod.startswith("models/"):
            mod = mod[len("models/"):]

        # Deprecation compatibility table: remap decommissioned legacy models to active models
        LEGACY_GEMINI_REMAP = {
            "gemini-1.0-pro": "gemini-3.5-flash-lite",
            "gemini-1.0": "gemini-3.5-flash-lite",
            "gemini-1.5-flash": "gemini-3.5-flash-lite",
            "gemini-1.5-pro": "gemini-flash-latest",
            "gemini-2.0-flash": "gemini-3.5-flash-lite",
            "gemini-2.0-flash-exp": "gemini-3.5-flash-lite",
            "gemini-2.5-flash": "gemini-3.5-flash-lite",
        }
        if mod in LEGACY_GEMINI_REMAP:
            target_mod = LEGACY_GEMINI_REMAP[mod]
            logger.warning(
                "Decommissioned Gemini model '%s' requested. Remapping to '%s'.",
                mod,
                target_mod,
            )
            mod = target_mod

        logger.info("Initializing ChatGoogleGenerativeAI [model: '%s']", mod)
        kwargs = {"model": mod, "temperature": temperature}
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens
        if key:
            kwargs["google_api_key"] = key
        return ChatGoogleGenerativeAI(**kwargs)
