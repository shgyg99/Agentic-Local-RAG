import os
from llama_index.core import (
    SimpleDirectoryReader,
    SummaryIndex,
    StorageContext,
    load_index_from_storage,
)

def get_index(data, index_name):
    index = None
    if not os.path.exists(index_name):
        print("building index", index_name)
        index = SummaryIndex.from_documents(data, show_progress=True)
        index.storage_context.persist(persist_dir=index_name)
    else:
        index = load_index_from_storage(StorageContext.from_defaults(persist_dir=index_name))
        
    return index


pdf_path = os.path.join("data", "Iran.pdf")
Iran_pdf = SimpleDirectoryReader(input_files=[pdf_path]).load_data()
Iran_index = get_index(Iran_pdf, "Iran")
Iran_engine = Iran_index.as_query_engine()
