from dataclasses import dataclass, field
import inspect
import pathlib
from typing import Callable

import dacite
import toml

from .tracer import Tracer
import constants


@dataclass
class Config:
    project: str
    output_template: str = field(default="{project}-{func_name}.pytype")


@dataclass
class PyTypesConfig:
    pytypes: Config


def _load_config(config_path: pathlib.Path) -> Config:
    cfg = toml.load(config_path.open())
    return dacite.from_dict(
        data_class=PyTypesConfig, data=cfg, config=dacite.Config(strict=True)
    )


def register(proj_root: pathlib.Path | None = None):
    """
    Register a test function for tracing.
    @param proj_root the path to project's root directory
    """

    def impl(test_function: Callable[[], None]):
        tracer = Tracer(project_dir=proj_root or pathlib.Path.cwd())
        setattr(test_function, constants.TRACER_ATTRIBUTE, tracer)
        return test_function

    return impl


def entrypoint(proj_root: pathlib.Path | None = None):
    """
    Execute and trace all registered test functions in the same module as the marked function
    @param proj_root the path to project's root directory, which contains `pytypes.toml`
    """
    root = proj_root or pathlib.Path.cwd()
    cfg = _load_config(root / constants.CONFIG_FILE_NAME)

    def impl(main: Callable[[], None]):
        main()
        prev_frame = inspect.currentframe().f_back

        for fname, function in prev_frame.f_globals.items():
            if not inspect.isfunction(function) or not hasattr(
                function, constants.TRACER_ATTRIBUTE
            ):
                continue

            substituted_output = cfg.pytypesoutput_template.format_map(
                {"project": cfg.pytypesproject, "func_name": fname}
            )
            tracer = getattr(function, constants.TRACER_ATTRIBUTE)
            # delattr(function, constants.TRACER_ATTRIBUTE)

            with tracer.active_trace():
                function()

            tracer.trace_data.to_pickle(str(tracer.project_dir / substituted_output))

    return impl
