"""Which voice model suits this computer.

The two models are the same voice: kokoro.int8.onnx compressed to 8-bit
numbers (setting value "cpu", shown as Standard) and kokoro.onnx uncompressed
("gpu", shown as Full precision). Both run on the processor. Which one is
faster depends on the processor: on an Apple M4 they run at about the same
speed, so the smaller one is chosen there; on an Intel Core Ultra 7 155U
(Windows) the full-precision model voiced 4 to 5 times faster (October 2026),
so Intel and AMD processors get that one.

No heavy imports here: the installers and the settings model both use it.
"""

import platform

_X86 = {"x86_64", "amd64", "i386", "i686", "x86"}


def processor_kind() -> str:
    """'x86' for Intel and AMD processors, 'apple' for Apple's, else 'other'."""
    machine = platform.machine().lower()
    if machine in _X86:
        return "x86"
    if platform.system() == "Darwin" and machine in ("arm64", "aarch64"):
        return "apple"
    return "other"


def default_engine_mode() -> str:
    """The model to use unless the person chose otherwise: 'gpu' (full
    precision) on Intel and AMD processors, 'cpu' (compressed) elsewhere."""
    return "gpu" if processor_kind() == "x86" else "cpu"
