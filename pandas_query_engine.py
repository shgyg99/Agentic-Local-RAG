"""Local PandasQueryEngine compatibility module.

The LlamaIndex core package now exposes only a deprecation stub for this
engine, while llama-index-experimental imports unrelated optional modules at
package import time. This module keeps the pandas-only behavior used by the app.
"""

import ast
import copy
import logging
import sys
import traceback
from types import CodeType, ModuleType
from typing import Any, Dict, Mapping, Optional, Sequence, Union

import numpy as np
import pandas as pd
from llama_index.core.base.base_query_engine import BaseQueryEngine
from llama_index.core.base.response.schema import Response
from llama_index.core.indices.struct_store.pandas import PandasIndex
from llama_index.core.llms.llm import LLM
from llama_index.core.output_parsers import BaseOutputParser
from llama_index.core.output_parsers.utils import parse_code_markdown
from llama_index.core.prompts import BasePromptTemplate, PromptTemplate, PromptType
from llama_index.core.prompts.mixin import PromptDictType, PromptMixinType
from llama_index.core.schema import QueryBundle
from llama_index.core.settings import Settings
from llama_index.core.utils import print_text

logger = logging.getLogger(__name__)

ALLOWED_IMPORTS = {
    "math",
    "time",
    "datetime",
    "pandas",
    "numpy",
    "matplotlib",
    "plotly",
    "seaborn",
}

ALLOWED_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "ascii": ascii,
    "bin": bin,
    "bool": bool,
    "bytearray": bytearray,
    "bytes": bytes,
    "chr": chr,
    "complex": complex,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hash": hash,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
}


def _restricted_import(
    name: str,
    globals: Union[Mapping[str, object], None] = None,
    locals: Union[Mapping[str, object], None] = None,
    fromlist: Sequence[str] = (),
    level: int = 0,
) -> ModuleType:
    if name in ALLOWED_IMPORTS:
        return __import__(name, globals, locals, fromlist, level)
    raise ImportError(f"Import of module '{name}' is not allowed")


ALLOWED_BUILTINS["__import__"] = _restricted_import


def _get_restricted_globals(__globals: Union[dict, None]) -> Any:
    restricted_globals = copy.deepcopy(ALLOWED_BUILTINS)
    if __globals:
        restricted_globals.update(__globals)
    return restricted_globals


class DunderVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.has_access_to_private_entity = False
        self.has_access_to_disallowed_builtin = False
        builtins = globals()["__builtins__"].keys()
        self._builtins = builtins

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("_"):
            self.has_access_to_private_entity = True
        if node.id not in ALLOWED_BUILTINS and node.id in self._builtins:
            self.has_access_to_disallowed_builtin = True
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            self.has_access_to_private_entity = True
        if node.attr not in ALLOWED_BUILTINS and node.attr in self._builtins:
            self.has_access_to_disallowed_builtin = True
        self.generic_visit(node)


def _contains_protected_access(code: str) -> bool:
    tree = ast.parse(code)
    imports_modules = any(
        isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.iter_child_nodes(tree)
    )
    dunder_visitor = DunderVisitor()
    dunder_visitor.visit(tree)
    return (
        dunder_visitor.has_access_to_private_entity
        or dunder_visitor.has_access_to_disallowed_builtin
        or imports_modules
    )


def _verify_source_safety(__source: Union[str, bytes, CodeType]) -> None:
    if isinstance(__source, CodeType):
        raise RuntimeError("Direct execution of CodeType is forbidden.")
    if isinstance(__source, bytes):
        __source = __source.decode()
    if _contains_protected_access(__source):
        raise RuntimeError(
            "Execution of code containing private access, disallowed builtins, "
            "or imports is forbidden."
        )


def safe_eval(
    __source: Union[str, bytes, CodeType],
    __globals: Union[Dict[str, Any], None] = None,
    __locals: Union[Mapping[str, object], None] = None,
) -> Any:
    _verify_source_safety(__source)
    return eval(__source, _get_restricted_globals(__globals), __locals)


def safe_exec(
    __source: Union[str, bytes, CodeType],
    __globals: Union[Dict[str, Any], None] = None,
    __locals: Union[Mapping[str, object], None] = None,
) -> None:
    _verify_source_safety(__source)
    return exec(__source, _get_restricted_globals(__globals), __locals)


DEFAULT_PANDAS_TMPL = (
    "You are working with a pandas dataframe in Python.\n"
    "The name of the dataframe is `df`.\n"
    "This is the result of `print(df.head())`:\n"
    "{df_str}\n\n"
    "Follow these instructions:\n"
    "{instruction_str}\n"
    "Query: {query_str}\n\n"
    "Expression:"
)

DEFAULT_PANDAS_PROMPT = PromptTemplate(
    DEFAULT_PANDAS_TMPL, prompt_type=PromptType.PANDAS
)

DEFAULT_INSTRUCTION_STR = (
    "1. Convert the query to executable Python code using Pandas.\n"
    "2. The final line of code should be a Python expression that can be called with the `eval()` function.\n"
    "3. The code should represent a solution to the query.\n"
    "4. PRINT ONLY THE EXPRESSION.\n"
    "5. Do not quote the expression.\n"
)

DEFAULT_RESPONSE_SYNTHESIS_PROMPT_TMPL = (
    "Given an input question, synthesize a response from the query results.\n"
    "Query: {query_str}\n\n"
    "Pandas Instructions (optional):\n{pandas_instructions}\n\n"
    "Pandas Output: {pandas_output}\n\n"
    "Response: "
)
DEFAULT_RESPONSE_SYNTHESIS_PROMPT = PromptTemplate(
    DEFAULT_RESPONSE_SYNTHESIS_PROMPT_TMPL,
)


def default_output_processor(
    output: str, df: pd.DataFrame, **output_kwargs: Any
) -> str:
    if sys.version_info < (3, 9):
        logger.warning(
            "Python version must be >= 3.9 to execute the Pandas query. "
            "Returning the raw Python instructions instead."
        )
        return output

    local_vars = {"df": df, "pd": pd}
    global_vars = {"np": np}
    output = parse_code_markdown(output, only_last=True)
    if not isinstance(output, str):
        output = output[0]

    try:
        tree = ast.parse(output)
        module = ast.Module(tree.body[:-1], type_ignores=[])
        safe_exec(ast.unparse(module), {}, local_vars)
        module_end = ast.Module(tree.body[-1:], type_ignores=[])
        module_end_str = ast.unparse(module_end)
        if module_end_str.strip("'\"") != module_end_str:
            module_end_str = safe_eval(module_end_str, global_vars, local_vars)

        current_max_colwidth = pd.get_option("display.max_colwidth")
        current_max_rows = pd.get_option("display.max_rows")
        current_max_columns = pd.get_option("display.max_columns")
        if "max_colwidth" in output_kwargs:
            pd.set_option("display.max_colwidth", output_kwargs["max_colwidth"])
        if "max_rows" in output_kwargs:
            pd.set_option("display.max_rows", output_kwargs["max_rows"])
        if "max_columns" in output_kwargs:
            pd.set_option("display.max_columns", output_kwargs["max_columns"])
        output_str = str(safe_eval(module_end_str, global_vars, local_vars))
        pd.set_option("display.max_colwidth", current_max_colwidth)
        pd.set_option("display.max_rows", current_max_rows)
        pd.set_option("display.max_columns", current_max_columns)
        return output_str
    except Exception as exc:
        traceback.print_exc()
        return (
            "There was an error running the output as Python code. "
            f"Error message: {exc}"
        )


class PandasInstructionParser(BaseOutputParser):
    def __init__(
        self, df: pd.DataFrame, output_kwargs: Optional[Dict[str, Any]] = None
    ) -> None:
        self.df = df
        self.output_kwargs = output_kwargs or {}

    def parse(self, output: str) -> Any:
        return default_output_processor(output, self.df, **self.output_kwargs)


class PandasQueryEngine(BaseQueryEngine):
    def __init__(
        self,
        df: pd.DataFrame,
        instruction_str: Optional[str] = None,
        instruction_parser: Optional[PandasInstructionParser] = None,
        pandas_prompt: Optional[BasePromptTemplate] = None,
        output_kwargs: Optional[dict] = None,
        head: int = 5,
        verbose: bool = False,
        llm: Optional[LLM] = None,
        synthesize_response: bool = False,
        response_synthesis_prompt: Optional[BasePromptTemplate] = None,
        **kwargs: Any,
    ) -> None:
        self._df = df
        self._head = head
        self._pandas_prompt = pandas_prompt or DEFAULT_PANDAS_PROMPT
        self._instruction_str = instruction_str or DEFAULT_INSTRUCTION_STR
        self._instruction_parser = instruction_parser or PandasInstructionParser(
            df, output_kwargs or {}
        )
        self._verbose = verbose
        self._llm = llm or Settings.llm
        self._synthesize_response = synthesize_response
        self._response_synthesis_prompt = (
            response_synthesis_prompt or DEFAULT_RESPONSE_SYNTHESIS_PROMPT
        )
        super().__init__(callback_manager=Settings.callback_manager)

    def _get_prompt_modules(self) -> PromptMixinType:
        return {}

    def _get_prompts(self) -> Dict[str, Any]:
        return {
            "pandas_prompt": self._pandas_prompt,
            "response_synthesis_prompt": self._response_synthesis_prompt,
        }

    def _update_prompts(self, prompts: PromptDictType) -> None:
        if "pandas_prompt" in prompts:
            self._pandas_prompt = prompts["pandas_prompt"]
        if "response_synthesis_prompt" in prompts:
            self._response_synthesis_prompt = prompts["response_synthesis_prompt"]

    @classmethod
    def from_index(cls, index: PandasIndex, **kwargs: Any) -> "PandasQueryEngine":
        logger.warning(
            "PandasIndex is deprecated. Directly construct PandasQueryEngine with df instead."
        )
        return cls(df=index.df, **kwargs)

    def _get_table_context(self) -> str:
        with pd.option_context("display.max_columns", None, "display.width", 1000):
            columns = ", ".join(repr(column) for column in self._df.columns)
            return f"Columns: [{columns}]\n{self._df.head(self._head)}"

    def _query(self, query_bundle: QueryBundle) -> Response:
        context = self._get_table_context()
        pandas_response_str = self._llm.predict(
            self._pandas_prompt,
            df_str=context,
            query_str=query_bundle.query_str,
            instruction_str=self._instruction_str,
        )

        if self._verbose:
            print_text(f"> Pandas Instructions:\n```\n{pandas_response_str}\n```\n")
        pandas_output = self._instruction_parser.parse(pandas_response_str)
        if self._verbose:
            print_text(f"> Pandas Output: {pandas_output}\n")

        response_metadata = {
            "pandas_instruction_str": pandas_response_str,
            "raw_pandas_output": pandas_output,
        }
        if self._synthesize_response:
            response_str = str(
                self._llm.predict(
                    self._response_synthesis_prompt,
                    query_str=query_bundle.query_str,
                    pandas_instructions=pandas_response_str,
                    pandas_output=pandas_output,
                )
            )
        else:
            response_str = str(pandas_output)

        return Response(response=response_str, metadata=response_metadata)

    async def _aquery(self, query_bundle: QueryBundle) -> Response:
        return self._query(query_bundle)


NLPandasQueryEngine = PandasQueryEngine
GPTNLPandasQueryEngine = PandasQueryEngine
