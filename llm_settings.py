import os

from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI


def configure_llama_index():
    load_dotenv()

    api_key = os.getenv("API_KEY")
    api_url = os.getenv("API_URL")
    api_model = os.getenv("API_MODEL")
    embed_model = os.getenv("EMBED_MODEL", "text-embedding-ada-002")

    llm_config = {}
    embed_config = {"model": embed_model}

    if api_key:
        llm_config["api_key"] = api_key
        embed_config["api_key"] = api_key

    if api_url:
        llm_config["api_base"] = api_url
        embed_config["api_base"] = api_url

    if api_model:
        llm_config["model"] = api_model

    llm = OpenAI(**llm_config)
    Settings.llm = llm
    Settings.embed_model = OpenAIEmbedding(**embed_config)

    return llm
