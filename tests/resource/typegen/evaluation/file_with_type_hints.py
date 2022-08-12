import pathlib
from pathlib import Path
from pathlib import PosixPath, WindowsPath
import numpy as np
from typegen import evaluation

class A:
    def __init__(self):
        self.string: WindowsPath = WindowsPath("string")
        self.array: np.ndarray = np.zeros((3, 3))
        self.not_annotated_member = False

        x: evaluation.FileTypeHintsCollector = ...

    def function(self, a: pathlib.Path, b: Path) -> bool:
        c: bool; d = a == b, 10
        e: str = str(d)
        f: object = None; g: float = 3.14
        return c


class B(A):
    def function(self, a: pathlib.Path, b: Path) -> bool:
        return not super().function(a, b)


def evaluate(instance: A) -> None:
    pass


def main():
    instance1: A = A()
    instance2: B = B()
    evaluate(instance1)
    evaluate(instance2)
    assert instance1.function(Path("a"), PosixPath("a"))
    assert not instance2.function(Path("a"), PosixPath("a"))
