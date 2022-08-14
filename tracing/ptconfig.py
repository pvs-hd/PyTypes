from dataclasses import dataclass, field, asdict
import pathlib
import typing

import dacite
from dacite.exceptions import DaciteError
import toml

import constants


@dataclass
class PyTypes:
    project: str

    stdlib_path: pathlib.Path
    proj_path: pathlib.Path
    venv_path: pathlib.Path
    benchmark_performance: bool = False

    output_template: str = field(
        default="pytypes/{project}/{test_case}/{func_name}" + constants.TRACE_DATA_FILE_ENDING
    )
    output_npy_template: str = field(
        default="pytypes/{project}/{test_case}/{func_name}" + constants.NP_ARRAY_FILE_ENDING
    )


@dataclass
class Dedup:
    name: str
    kind: typing.Literal["dedup"] = "dedup"


@dataclass
class DropTest:
    name: str
    test_name_pat: str
    kind: typing.Literal["drop_test"] = "drop_test"


@dataclass
class DropVars:
    name: str
    kind: typing.Literal["drop_mult_var"] = "drop_mult_var"
    min_amount_types_to_drop: int | None = 2


@dataclass
class ReplaceSubtypes:
    name: str
    kind: typing.Literal["repl_subty"] = "repl_subty"
    only_replace_if_base_was_traced: bool | None = False


@dataclass
class KeepFirst:
    name: str
    kind: typing.Literal["keep_only_first"] = "keep_only_first"


@dataclass
class MinThreshold:
    name: str
    kind: typing.Literal["drop_min_threshold"] = "drop_min_threshold"
    min_threshold: float = 0.25


# https://github.com/konradhalas/dacite/pull/184
# the cooler union syntax is not supported
Unifier = typing.Union[Dedup, DropTest, DropVars, ReplaceSubtypes, KeepFirst, MinThreshold]


@dataclass
class TomlCfg:
    pytypes: PyTypes
    unifier: list[Unifier] = field(default_factory=list)


def load_config(config_path: pathlib.Path) -> TomlCfg:
    cfg = toml.load(config_path.open())

    try:
        return dacite.from_dict(
            data_class=TomlCfg,
            data=cfg,
            config=dacite.Config(
                cast=[pathlib.Path],
                strict=True,
                strict_unions_match=True,
            ),
        )

    except DaciteError as e:
        print(f"Failed to load config from {config_path}")
        raise e


def write_config(config_path: pathlib.Path, pttoml: TomlCfg):
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Not the nicest way to do this, but Path's repr operator
    # leaves "PosixPath" in the config file
    pttoml.pytypes.proj_path = str(pttoml.pytypes.proj_path)  # type: ignore
    pttoml.pytypes.stdlib_path = str(pttoml.pytypes.stdlib_path)  # type: ignore
    pttoml.pytypes.venv_path = str(pttoml.pytypes.venv_path)  # type: ignore

    ad = asdict(pttoml)
    ad["pytypes"].pop("output_template")

    toml.dump(ad, config_path.open("w"))
