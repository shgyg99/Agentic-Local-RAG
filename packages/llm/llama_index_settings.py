from typing import Any

from llama_index.core import Settings as LlamaIndexSettings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

from packages.core.settings import get_settings


def configure_llama_index():
    settings = get_settings()
    settings.require_llm_settings()

    llm_config: dict[str, Any] = {}
    embed_config: dict[str, Any] = {"model": settings.embed_model}

    if settings.api_key:
        llm_config["api_key"] = settings.api_key
        embed_config["api_key"] = settings.api_key

    if settings.api_url:
        llm_config["api_base"] = settings.api_url
        embed_config["api_base"] = settings.api_url

    if settings.api_model:
        llm_config["model"] = settings.api_model

    llm = OpenAI(**llm_config)
    LlamaIndexSettings.llm = llm
    LlamaIndexSettings.embed_model = OpenAIEmbedding(**embed_config)

    return llm
