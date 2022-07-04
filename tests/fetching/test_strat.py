import pathlib
import pytest
from unittest import mock

from fetching.projio import Project

from fetching.strat import PyTestStrategy

cwd = pathlib.Path.cwd() / "tests" / "resource" / "sample_decorator_appender_folder"


@pytest.fixture()
def project_folder():
    with mock.patch(
        "fetching.projio.Project.test_directory",
        new_callable=mock.PropertyMock,
    ) as m:
        m.return_value = cwd
        p = Project(cwd)

        yield p


def test_if_test_object_searches_for_test_files_in_folders_it_generates_test_files(
    project_folder,
):
    test_object = PyTestStrategy(
        pathlib.Path.cwd(), overwrite_tests=False, recurse_into_subdirs=True
    )
    test_object.apply(project_folder)
    test_file_paths = list(
        filter(
            lambda s: not s.name.endswith(PyTestStrategy.SUFFIX), cwd.glob("test_*.py")
        )
    )
    new_test_file_paths = list(map(
        lambda p: p.parent / f"{p.stem}{PyTestStrategy.SUFFIX}", test_file_paths
    ))
    assert len(new_test_file_paths) != 0

    for new_test_file_path in new_test_file_paths:
        assert new_test_file_path.exists()


def test_if_test_object_searches_for_test_files_in_folders_including_subfolders_it_overwrites_test_files(
    project_folder,
):
    test_object = PyTestStrategy(pathlib.Path.cwd(), overwrite_tests=True, recurse_into_subdirs=True)
    test_object.apply(project_folder)
    test_file_paths = list(cwd.glob("test_*.py"))

    for test_file_paths in test_file_paths:
        assert test_file_paths.exists()