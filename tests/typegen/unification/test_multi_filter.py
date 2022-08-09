import os
import pathlib
from typegen.unification.drop_dupes import DropDuplicatesFilter
from typegen.unification.drop_vars import DropVariablesOfMultipleTypesFilter

from typegen.unification.filter_base import TraceDataFilter, TraceDataFilterList
from typegen.unification.drop_test_func import DropTestFunctionDataFilter
from typegen.unification.subtyping import ReplaceSubTypesFilter

from .data import get_sample_trace_data

import constants


def test_factory():
    container = TraceDataFilter(ident=TraceDataFilterList.ident)
    assert isinstance(container, TraceDataFilterList)


def test_trace_data_filter_list_processes_and_returns_correct_data():
    expected_trace_data = get_sample_trace_data().iloc[[4, 5, 7]].reset_index(drop=True)
    expected_trace_data = expected_trace_data.astype(constants.TraceData.SCHEMA)

    drop_test_function_data_filter = TraceDataFilter(
        ident=DropTestFunctionDataFilter.ident, test_func_name_pattern="test_"
    )

    drop_duplicates_filter = TraceDataFilter(DropDuplicatesFilter.ident)

    proj_path = pathlib.Path.cwd()
    venv_path = os.environ["VIRTUAL_ENV"]
    replace_subtypes_filter = TraceDataFilter(
        ReplaceSubTypesFilter.ident,
        proj_path=proj_path,
        venv_path=venv_path,
        only_replace_if_base_was_traced=True,
    )
    drop_variables_of_multiple_types_filter = TraceDataFilter(
        ident=DropVariablesOfMultipleTypesFilter.ident
    )

    multi_filter = TraceDataFilter(ident=TraceDataFilterList.ident)
    multi_filter.append(drop_test_function_data_filter)
    multi_filter.append(drop_duplicates_filter)
    multi_filter.append(replace_subtypes_filter)
    multi_filter.append(drop_duplicates_filter)
    multi_filter.append(drop_variables_of_multiple_types_filter)

    trace_data = get_sample_trace_data()
    actual_trace_data = multi_filter.apply(trace_data)

    assert expected_trace_data.equals(actual_trace_data)
