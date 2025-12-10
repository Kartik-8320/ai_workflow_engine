# app package initializer
# Optionally import submodules here if you want them to run on package import.
# This is convenient so that node/tool registration happens automatically.

# Import agents package to ensure agents' modules are loaded (they register nodes/tools)
from . import agents  # noqa: F401
