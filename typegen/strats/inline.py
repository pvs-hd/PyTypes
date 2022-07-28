import ast
import functools
import logging
import operator
import pathlib
import itertools

from constants import TraceData
from tracing.trace_data_category import TraceDataCategory
from typegen.strats.gen import Generator

import pandas as pd

logger = logging.getLogger(__name__)

# It is important to handle sub-nodes from their parent node, as line numbering may differ across multi line statements
class TypeHintApplierVisitor(ast.NodeTransformer):
    def __init__(self, relevant: pd.DataFrame) -> None:
        super().__init__()
        self.df = relevant


    def generic_visit(self, node: ast.AST) -> ast.AST:
        # Track ClassDefs and FunctionDefs to disambiguate
        # functions from methods
        if isinstance(node, ast.ClassDef):
            for child in filter(lambda c: isinstance(c, ast.FunctionDef), node.body):
                child.parent = node # type: ignore

        return super().generic_visit(node)

    def visit_FunctionDef(self, fdef: ast.FunctionDef):
        logger.debug(f"Applying hints to '{fdef.name}'")
        # NOTE: disregards *args (fdef.vararg) and **kwargs (fdef.kwarg)

        # parameters
        param_masks = [
            self.df[TraceData.CATEGORY] == TraceDataCategory.FUNCTION_ARGUMENT,
            self.df[TraceData.FUNCNAME] == fdef.name,
        ]
        params = self.df[functools.reduce(operator.and_, param_masks)]

        for arg in itertools.chain(fdef.args.posonlyargs, fdef.args.args):
            # Narrow by line number and identifier
            arg_hint_mask = [
                params[TraceData.LINENO] == arg.lineno,
                params[TraceData.VARNAME] == arg.arg,
            ]
            arg_hints = params[functools.reduce(operator.and_, arg_hint_mask)]
            assert (
                arg_hints.shape[0] <= 1
            ), f"Found multiple hints for the parameter type: {arg_hints}"

            # no type hint, skip
            if arg_hints.shape[0] == 0:
                logger.debug(f"No hint found for '{arg.arg}'")
                continue

            arg_hint = arg_hints[TraceData.VARTYPE].values[0]
            logger.debug(f"Applying hint '{arg_hint}' to '{arg.arg}'")
            arg.annotation = ast.Name(arg_hint)

        # disambiguate methods from functions
        if hasattr(fdef, "parent"):
            rettype_masks = [
                self.df[TraceData.CATEGORY] == TraceDataCategory.FUNCTION_RETURN,
                self.df[TraceData.CLASS] == fdef.parent.name, # type: ignore
                self.df[TraceData.VARNAME] == fdef.name,
                self.df[TraceData.LINENO] == 0,  # return type, always stored at line 0
            ]
        
        else:
            rettype_masks = [
                self.df[TraceData.CATEGORY] == TraceDataCategory.FUNCTION_RETURN,
                self.df[TraceData.CLASS].isnull(),
                self.df[TraceData.VARNAME] == fdef.name,
                self.df[TraceData.LINENO] == 0,
            ]

        
        rettypes = self.df[functools.reduce(operator.and_, rettype_masks)]

        assert (
            rettypes.shape[0] <= 1
        ), f"Found multiple hints for the return type: {arg_hint}"

        # no type hint, skip
        if rettypes.shape[0] == 0:
            logger.debug(f"No hint found for return for '{fdef.name}'")

        if rettypes.shape[0] == 1:
            ret_hint = rettypes[TraceData.VARTYPE].values[0]
            logger.debug(f"Applying return type hint '{ret_hint}' to '{fdef.name}'")
            fdef.returns = ast.Name(ret_hint)

        return fdef


class InlineGenerator(Generator):
    ident = "inline"

    def _gen_hints(self, applicable: pd.DataFrame, nodes: ast.AST) -> ast.AST:
        visitor = TypeHintApplierVisitor(applicable)
        visitor.visit(nodes)

        return nodes

    def _store_hints(self, source_file: pathlib.Path, hinting: ast.AST) -> None:
        # Inline means overwriting the original
        contents = ast.unparse(hinting)
        with source_file.open("w") as f:
            f.write(contents)
