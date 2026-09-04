"""
Warning filters that must be installed before pandas is imported.

pytest applies its own ``filterwarnings`` config once collection starts, which
is too late for warnings raised while a module is being imported. pandas emits
two of those at import time, notices that the optional ``numexpr`` and
``bottleneck`` accelerators are older than it would like. Neither package is
used by this project and pandas falls back to its own implementations, so the
notices carry no information for us.

This file is imported before the test modules that pull in pandas, which is the
only reason the filters land in time. Everything else is left to pytest.ini,
which is the single place the warning policy is documented. Nothing here
ignores a category wholesale.
"""

import warnings

for _pkg in ("numexpr", "bottleneck"):
    warnings.filterwarnings(
        "ignore",
        message=rf"Pandas requires version .* of '{_pkg}'",
        category=UserWarning,
    )
