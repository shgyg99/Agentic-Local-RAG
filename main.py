from dotenv import load_dotenv
import asyncio
import os
import pandas as pd
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from pandas_query_engine import PandasQueryEngine
from prompts import new_prompt, instruction_str, context
from note_engine import note_engine
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")
API_MODEL = os.getenv("API_MODEL")
API_EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-ada-002")

llm_config = {}
embed_config = {"model": API_EMBED_MODEL}
if API_KEY:
    llm_config["api_key"] = API_KEY
    embed_config["api_key"] = API_KEY
    if API_URL:
        llm_config["api_base"] = API_URL
        embed_config["api_base"] = API_URL
    if API_MODEL:
        llm_config["model"] = API_MODEL
        embed_config["model"] = API_EMBED_MODEL

llm = OpenAI(**llm_config)
Settings.llm = llm
Settings.embed_model = OpenAIEmbedding(**embed_config)

from pdf import Iran_engine

population_path = os.path.join("data", "population.csv")
population_df = pd.read_csv(population_path)

population_query_engine = PandasQueryEngine(df=population_df, verbose=True, instruction_str=instruction_str)
population_query_engine.update_prompts({"pandas_prompt": new_prompt})


tools = [
    note_engine,
    QueryEngineTool(query_engine=population_query_engine, metadata=ToolMetadata(
        name="population_data",
        description="this gives information at the world population and demographics"
    )),
    QueryEngineTool(query_engine=Iran_engine, metadata=ToolMetadata(
        name="Iran_data",
        description="this gives detailed information about Iran the country."
    ))
]

agent = ReActAgent(tools=tools, llm=llm, verbose=True, system_prompt=context)


async def run_agent(prompt: str):
    return await agent.run(user_msg=prompt)

while (prompt := input("Enter a prompt (q to quit): ")) != "q":
    result = asyncio.run(run_agent(prompt))
    print(result)
