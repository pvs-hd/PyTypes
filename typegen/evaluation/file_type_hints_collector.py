import os.path
import pathlib
import pandas as pd
import libcst as cst
from libcst.metadata import PositionProvider
import constants
from tracing import TraceDataCategory


class FileTypeHintsCollector:
    """Collects the type hints of multiple .py files."""
    def __init__(self, project_dir: pathlib.Path):
        self.project_dir = project_dir
        self.typehint_data = pd.DataFrame(columns=constants.TraceData.TYPE_HINT_SCHEMA.keys())

    def collect_data(self, file_paths: list[pathlib.Path]) -> None:
        """Collects the type hints of the provided file paths."""
        for file_path in file_paths:
            if not file_path.is_relative_to(self.project_dir):
                raise ValueError(str(file_path) + " is not relative to " + str(self.project_dir) + ".")

            with file_path.open() as file:
                file_content = file.read()

            module = cst.parse_module(source=file_content)
            module_and_meta = cst.MetadataWrapper(module)
            relative_path = file_path.relative_to(self.project_dir)
            visitor = _TypeHintVisitor(relative_path)
            module_and_meta.visit(visitor)
            typehint_data = pd.DataFrame(visitor.typehint_data, columns=constants.TraceData.TYPE_HINT_SCHEMA.keys())

            self.typehint_data = pd.concat(
                [self.typehint_data, typehint_data], ignore_index=True
            ).astype(constants.TraceData.TYPE_HINT_SCHEMA)


class _TypeHintVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self.file_path = file_path
        self.typehint_data = []
        self._scope_stack: list[cst.FunctionDef | cst.ClassDef] = []
        self.imports: dict[str, str] = {}
        self.imports_alias: dict[str, str] = {}

    def _innermost_class(self) -> cst.ClassDef | None:
        fromtop = reversed(self._scope_stack)
        classes = filter(lambda p: isinstance(p, cst.ClassDef), fromtop)

        first: cst.ClassDef | None = next(classes, None)  # type: ignore
        return first

    def _innermost_function(self) -> cst.FunctionDef | None:
        fromtop = reversed(self._scope_stack)
        fdefs = filter(lambda p: isinstance(p, cst.FunctionDef), fromtop)

        first: cst.FunctionDef | None = next(fdefs, None)  # type: ignore
        return first

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool | None:
        if isinstance(node.module, cst.Name):
            module_name: str = node.module.value
            try:
                iterator = iter(node.names)
                for name in iterator:
                    imported_element_name: str = name.name.value
                    self.imports[imported_element_name] = module_name
            except TypeError:
                pass
        else:
            raise NotImplementedError(type(node.module))
        return True

    def visit_Import(self, node: "Import") -> bool | None:
        try:
            iterator = iter(node.names)
            for name in iterator:
                if name.evaluated_alias is None:
                    continue
                module_name: str = name.evaluated_name
                module_alias: str = name.evaluated_alias
                self.imports_alias[module_alias] = module_name
        except TypeError:
            pass

    def visit_ClassDef(self, cdef: cst.ClassDef) -> bool | None:
        # Track ClassDefs to disambiguate functions from methods
        self._scope_stack.append(cdef)
        return True

    def leave_ClassDef(self, _: cst.ClassDef) -> None:
        self._scope_stack.pop()

    def visit_FunctionDef(self, fdef: cst.FunctionDef) -> bool | None:
        # Track assignments from Functions
        # NOTE: this handles nested functions too, because the parent reference gets overwritten
        # NOTE: before we start generating hints for its children
        self._scope_stack.append(fdef)
        return True

    def leave_FunctionDef(self, fdef: cst.FunctionDef) -> None:
        self._scope_stack.pop()

    def visit_Param(self, node: cst.Param) -> bool | None:
        if not hasattr(node, "annotation") or node.annotation is None:
            return True
        variable_name = self._get_variable_name(node)
        line_number = self._get_line_number(node)
        type_hint = self._get_annotation_value(node.annotation)
        self._add_row(line_number, TraceDataCategory.FUNCTION_PARAMETER, variable_name, type_hint)
        return True

    def visit_FunctionDef_returns(self, node: cst.FunctionDef) -> None:
        variable_name = self._get_variable_name(node)
        line_number = self._get_line_number(node)
        if node.returns:
            type_hint = self._get_annotation_value(node.returns)
        else:
            type_hint = None
        self._add_row(line_number, TraceDataCategory.FUNCTION_RETURN, variable_name, type_hint)

    def visit_AnnAssign(self, node: cst.AnnAssign) -> bool | None:
        line_number = self._get_line_number(node)

        type_hint = self._get_annotation_value(node.annotation)
        if isinstance(node.target, cst.Attribute):
            category = TraceDataCategory.CLASS_MEMBER
            variable_name = node.target.attr.value
        elif isinstance(node.target, cst.Name):
            category = TraceDataCategory.LOCAL_VARIABLE
            variable_name = node.target.value
        else:
            raise TypeError("Unhandled case for: " + type(node.annotation.annotation).__name__)
        self._add_row(line_number, category, variable_name, type_hint)
        return True

    def _get_variable_name(self, node: cst.FunctionDef | cst.Param):
        return node.name.value

    def _get_line_number(self, node: cst.CSTNode):
        pos = self.get_metadata(PositionProvider, node).start
        variable_line_number = pos.line
        return variable_line_number

    def _add_row(self, line_number: int, category: TraceDataCategory, variable_name: str | None, type_hint: str | None):
        class_node = self._innermost_class()
        class_name = None
        if class_node:
            class_name = class_node.name.value
        function_node = self._innermost_function()
        function_name = None
        if function_node:
            function_name = function_node.name.value
        self.typehint_data.append([
            self.file_path,
            class_name,
            function_name,
            line_number,
            category,
            variable_name,
            type_hint,
        ])

    def _get_annotation_value(self, annotation: cst.Annotation | None) -> str | None:
        if annotation is None:
            return None

        actual_annotation = annotation.annotation
        if isinstance(actual_annotation, cst.Attribute) and isinstance(actual_annotation.value, cst.Name):
            module_name = actual_annotation.value.value
            type_name = actual_annotation.attr.value
        elif isinstance(actual_annotation, cst.Name):
            module_name = None
            type_name = actual_annotation.value
            if type_name in self.imports.keys():
                module_name = self.imports[type_name]
        else:
            raise TypeError("Unhandled case for: " + type(actual_annotation).__name__)

        if module_name is None:
            current_annotation = type_name
            if "." not in current_annotation:
                return current_annotation
        else:
            current_annotation = module_name + "." + type_name

        splits = current_annotation.split(".", 1)
        first_module_element = splits[0]
        remaining_annotation = splits[1]

        # If the first element is an alias, replaces it with the actual module name.
        if first_module_element in self.imports_alias.keys():
            first_module_element = self.imports_alias[first_module_element]

        # If the first element is imported from a module, adds the module name.
        elif first_module_element in self.imports.keys():
            module_name = self.imports[first_module_element]
            first_module_element = module_name + "." + first_module_element

        return first_module_element + "." + remaining_annotation

