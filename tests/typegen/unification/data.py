import abc
import logging
import pathlib

import pandas as pd

import constants
from tracing.trace_data_category import TraceDataCategory

class BaseClass(abc.ABC):
    pass


class SubClass1(BaseClass):
    pass


class SubClass11(SubClass1):
    pass


class SubClass2(BaseClass):
    pass


class SubClass3(BaseClass):
    pass


def get_sample_trace_data() -> pd.DataFrame:
    trace_data = pd.DataFrame(columns=constants.TraceData.SCHEMA.keys())

    resource_path = pathlib.Path("tests", "typegen", "unification", "data.py")
    resource_module = "tests.typegen.unification.data"

    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "function_name",
        1,
        TraceDataCategory.FUNCTION_PARAMETER,
        "argument1",
        resource_module,
        "SubClass2",
    ]
    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "function_name",
        1,
        TraceDataCategory.FUNCTION_PARAMETER,
        "argument1",
        resource_module,
        "SubClass2",
    ]
    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "function_name",
        1,
        TraceDataCategory.FUNCTION_PARAMETER,
        "argument1",
        resource_module,
        "SubClass3",
    ]
    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "function_name",
        2,
        TraceDataCategory.LOCAL_VARIABLE,
        "local_variable1",
        resource_module,
        "SubClass11",
    ]
    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "function_name",
        2,
        TraceDataCategory.LOCAL_VARIABLE,
        "local_variable1",
        resource_module,
        "SubClass1",
    ]
    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "function_name",
        3,
        TraceDataCategory.LOCAL_VARIABLE,
        "local_variable2",
        resource_module,
        "SubClass1",
    ]
    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "function_name",
        3,
        TraceDataCategory.LOCAL_VARIABLE,
        "local_variable2",
        resource_module,
        "SubClass1",
    ]
    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "",
        0,
        TraceDataCategory.CLASS_MEMBER,
        "class_member1",
        resource_module,
        "SubClass1",
    ]
    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "",
        0,
        TraceDataCategory.CLASS_MEMBER,
        "class_member1",
        resource_module,
        "SubClass1",
    ]
    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "",
        0,
        TraceDataCategory.CLASS_MEMBER,
        "class_member1",
        resource_module,
        "SubClass11",
    ]
    trace_data.loc[len(trace_data.index)] = [
        str(resource_path),
        None,
        "BaseClass",
        "test_function_name",
        5,
        TraceDataCategory.LOCAL_VARIABLE,
        "local_variable",
        resource_module,
        "SubClass1",
    ]
    trace_data = trace_data.astype(constants.TraceData.SCHEMA)
    return trace_data

def test_trace_data_filter_list_processes_and_returns_correct_data():
    expected_trace_data = get_sample_trace_data().iloc[[4, 5, 7]].reset_index(drop=True)
    expected_trace_data = expected_trace_data.astype(constants.TraceData.SCHEMA)

    drop_test_function_data_filter = DropTestFunctionDataFilter(
        constants.PYTEST_FUNCTION_PATTERN
    )
    drop_duplicates_filter = DropDuplicatesFilter()
    replace_subtypes_filter = ReplaceSubTypesFilter(pathlib.Path.cwd(), None, True)
    drop_variables_of_multiple_types_filter = DropVariablesOfMultipleTypesFilter()

    test_filter = TraceDataFilterList()
    test_filter.append(drop_test_function_data_filter)
    test_filter.append(drop_duplicates_filter)
    test_filter.append(replace_subtypes_filter)
    test_filter.append(drop_duplicates_filter)
    test_filter.append(drop_variables_of_multiple_types_filter)

    trace_data = get_sample_trace_data()
    actual_trace_data = test_filter.apply(trace_data)

    assert expected_trace_data.equals(actual_trace_data)