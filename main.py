import asyncio

from llm_settings import configure_llama_index
from note_engine import note_engine
from pdf import get_query_engine
from prompts import context
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent


llm = configure_llama_index()
document_engine = get_query_engine()

tools = [
    note_engine,
    QueryEngineTool(query_engine=document_engine, metadata=ToolMetadata(
        name="pdf_documents",
        description="this answers questions using the indexed PDF documents."
    ))
]

agent = ReActAgent(tools=tools, llm=llm, verbose=True, system_prompt=context)


async def run_agent(prompt: str):
    return await agent.run(user_msg=prompt)

while (prompt := input("Enter a prompt (q to quit): ")) != "q":
    result = asyncio.run(run_agent(prompt))
    print(result)
