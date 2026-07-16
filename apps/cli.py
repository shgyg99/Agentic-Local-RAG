import asyncio
from typing import Any

from llama_index.core.agent import ReActAgent
from llama_index.core.tools import QueryEngineTool, ToolMetadata

from packages.ingestion.pdf import get_query_engine
from packages.llm.llama_index_settings import configure_llama_index
from packages.llm.prompts import context
from packages.notes.engine import note_engine

llm = configure_llama_index()
document_engine = get_query_engine()

tools: list[Any] = [
    note_engine,
    QueryEngineTool(
        query_engine=document_engine,
        metadata=ToolMetadata(
            name="pdf_documents",
            description="this answers questions using the indexed PDF documents.",
        ),
    ),
]

agent = ReActAgent(tools=tools, llm=llm, verbose=True, system_prompt=context)


async def run_agent(prompt: str):
    return await agent.run(user_msg=prompt)


while (prompt := input("Enter a prompt (q to quit): ")) != "q":
    result = asyncio.run(run_agent(prompt))
    print(result)
