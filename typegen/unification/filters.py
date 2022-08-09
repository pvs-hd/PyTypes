import logging
import operator
from abc import ABC, abstractmethod
from re import Pattern
import importlib
import pathlib
import os

from importlib.machinery import SourceFileLoader
import pandas as pd
from functools import reduce
from collections import Counter  # type: ignore

from pandas._libs.missing import NAType

import constants

from pprint import pprint


class TraceDataFilter(ABC):
    """Filters the trace data."""

    def __init__(self):
        pass

    @abstractmethod
    def apply(self, trace_data: pd.DataFrame) -> pd.DataFrame:
        """
        Processes the provided trace data and returns the processed trace data and the difference between the old and new data.

        @param trace_data The provided trace data to process.
        """
        pass


class DropDuplicatesFilter(TraceDataFilter):
    """Drops all duplicates in the trace data."""

    def __init__(self):
        super().__init__()

    def apply(self, trace_data: pd.DataFrame) -> pd.DataFrame:
        """
        Drops the duplicates in the provided trace data and returns the processed trace data.

        @param trace_data The provided trace data to process.
        """
        processed_trace_data = trace_data.drop_duplicates(ignore_index=True)
        return processed_trace_data.reset_index(drop=True)


class ReplaceSubTypesFilter(TraceDataFilter):
    """Replaces rows containing types in the data with their common base type."""

    def __init__(
        self,
        proj_root: pathlib.Path,
        venv_path: pathlib.Path,
        only_replace_if_base_type_already_in_data: bool = True,
    ):
        """
        @param only_replace_if_base_type_already_in_data Only replaces types if their common base type is already in the data.
        """
        super().__init__()
        self.proj_root = proj_root
        self.only_replace_if_base_type_already_in_data = (
            only_replace_if_base_type_already_in_data
        )

    def apply(self, trace_data: pd.DataFrame) -> pd.DataFrame:
        """
        Replaces the rows containing types with their common base type and returns the processed trace data. If
        only_replace_if_base_type_already_in_data is True, only rows of types whose base type is already in the data
        are replaced.

        @param trace_data The provided trace data to process.
        """
        subset = list(constants.TraceData.SCHEMA.keys())
        subset.remove(constants.TraceData.VARTYPE_MODULE)
        subset.remove(constants.TraceData.VARTYPE)
        subset.remove(constants.TraceData.FILENAME)
        grouped_trace_data = trace_data.groupby(subset, dropna=False)
        processed_trace_data = grouped_trace_data.apply(
            lambda group: self._update_group(trace_data, group)
        )
        logging.debug(f"Final result: {processed_trace_data}")
        return processed_trace_data.reset_index(drop=True).astype(constants.TraceData.SCHEMA)

    def _update_group(self, entire: pd.DataFrame, group):
        modules_with_types_in_group = group[
            [
                constants.TraceData.FILENAME,
                constants.TraceData.VARTYPE_MODULE,
                constants.TraceData.VARTYPE,
            ]
        ]
        basetype_module, basetype = self._get_common_base_type(
            modules_with_types_in_group
        )
        print(f"Base Type Module: {basetype_module}, Base Type: {basetype}")

        if self.only_replace_if_base_type_already_in_data:
            if basetype_module not in entire[constants.TraceData.VARTYPE_MODULE].values:
                logging.debug(
                    f"Not replacing module or type; module {basetype_module} not in traced {entire[constants.TraceData.VARTYPE_MODULE].unique()}"
                )
                return group

            if basetype not in entire[constants.TraceData.VARTYPE].values:
                logging.debug(
                    f"Not replacing module or type; type {basetype} not in traced {entire[constants.TraceData.VARTYPE].unique()}"
                )
                return group

        
        group[constants.TraceData.VARTYPE_MODULE] = basetype_module
        group[constants.TraceData.VARTYPE] = basetype
        return group

    def _get_common_base_type(
        self, modules_with_types: pd.DataFrame
    ) -> tuple[str, str]:
        type2bases = {}
        for _, row in modules_with_types.iterrows():
            varmodule, vartyp = (
                row[constants.TraceData.VARTYPE_MODULE],
                row[constants.TraceData.VARTYPE],
            )
            types_topologically_sorted = self._get_type_and_mro(varmodule, vartyp)

            # drop mros that are useless
            abcless = list(filter(lambda p: p[0] != "abc", types_topologically_sorted))
            type2bases[(varmodule, vartyp)] = abcless

        pprint(type2bases)

        # Pick shortest base types to minimise runtime
        smallest = min(type2bases.items(), key=lambda kv: len(kv[1]))
        smallest_bases = type2bases.pop(smallest[0])

        # Loop is guaranteed to return as all objects share "object" at a minimum
        for ty in smallest_bases:
            if all(ty in bases for bases in type2bases.values()):
                return ty

        raise AssertionError(
            f"MRO Search loop failed to terminate:\nNeedles: {smallest}, Haystack: {type2bases}"
        )

    def _get_type_and_mro(
        self, relative_type_module_name: str | None, variable_type_name: str
    ) -> list[tuple[str, str]]:
        print(relative_type_module_name, variable_type_name)

        if relative_type_module_name is not None:
            # recreate filename
            lookup_path = pathlib.Path(
                relative_type_module_name.replace(".", os.path.sep) + ".py"
            )

            # project import
            loader = SourceFileLoader(
                relative_type_module_name, str(self.proj_root / lookup_path)
            )
            spec = importlib.util.spec_from_loader(loader.name, loader)
            module = importlib.util.module_from_spec(spec)
            loader.exec_module(module)
            variable_type: type = getattr(module, variable_type_name)

            # TODO: venv import

            mros = variable_type.mro()

        module_and_name = list(map(lambda m: (m.__module__, m.__name__), mros))
        return module_and_name


"""         assert False

        if relative_type_module_name is not None and not isinstance(relative_type_module_name, NAType):
            try:
                loader = SourceFileLoader("temp", relative_type_module_name)
                spec = importlib.util.spec_from_loader(loader.name, loader)
                module = importlib.util.module_from_spec(spec)
                loader.exec_module(module)
                variable_type = getattr(module, variable_type_name)
            
        else:
            try:
                variable_type = globals()[variable_type_name]
            except KeyError:
                # Builtin type.
                return [variable_type_name, object.__name__]
        types_topologically_sorted = variable_type.mro()
        print(types_topologically_sorted)
        return [type_in_hierarchy.__name__ for type_in_hierarchy in types_topologically_sorted] """


class DropVariablesOfMultipleTypesFilter(TraceDataFilter):
    """Drops rows containing variables of multiple types."""

    def __init__(self, min_amount_types_to_drop: int = 2):
        """
        @param min_amount_types_to_drop The minimum amount of types to drop the data of the corresponding variable.
        """
        super().__init__()
        self.min_amount_types_to_drop = min_amount_types_to_drop

    def apply(self, trace_data: pd.DataFrame) -> pd.DataFrame:
        """
        Drops rows containing variables if the amount of inferred types is higher than self.min_amount_types_to_drop
        and returns the processed data.

        @param trace_data The provided trace data to process.
        """
        subset = list(constants.TraceData.SCHEMA.keys())
        subset.remove(constants.TraceData.VARTYPE)
        grouped_trace_data_with_unique_count = (
            trace_data.groupby(subset, dropna=False)[constants.TraceData.VARTYPE]
            .nunique()
            .reset_index(name="amount_types")
        )
        joined_trace_data = pd.merge(
            trace_data, grouped_trace_data_with_unique_count, on=subset, how="inner"
        )
        print(joined_trace_data)
        trace_data_with_dropped_variables = joined_trace_data[
            joined_trace_data["amount_types"] < self.min_amount_types_to_drop
        ]
        processed_data = trace_data_with_dropped_variables.drop(
            ["amount_types"], axis=1
        )
        return processed_data.reset_index(drop=True)


class TraceDataFilterList(TraceDataFilter):
    """Applies the filters in this list on the trace data."""

    def __init__(self):
        self.filters: list[TraceDataFilter] = []

    def append(self, trace_data_filter: TraceDataFilter) -> None:
        """Appends a filter to the list."""
        self.filters.append(trace_data_filter)

    def apply(self, trace_data: pd.DataFrame) -> pd.DataFrame:
        """
        Applies the filters on the provided trace data and returns the processed trace data.

        @param trace_data The provided trace data to process.
        """
        for trace_data_filter in self.filters:
            trace_data = trace_data_filter.apply(trace_data)

        return trace_data.copy().reset_index(drop=True)


class DropTestFunctionDataFilter(TraceDataFilter):
    """Drops all data about test functions."""

    def __init__(self, test_function_name_pattern: Pattern[str]):
        self.test_function_name_pattern: Pattern[str] = test_function_name_pattern

    def apply(self, trace_data: pd.DataFrame) -> pd.DataFrame:
        """Drops the data about test functions in the provided trace data and returns the processed trace data."""
        processed_trace_data = trace_data[
            ~trace_data[constants.TraceData.FUNCNAME].str.match(
                self.test_function_name_pattern
            )
        ]
        return processed_trace_data
