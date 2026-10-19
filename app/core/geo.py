"""The dashboard geography levels and how the reporting views carry them.

The cs_rpt_* views hold each level twice: `<level>_name`, the unit's display
name, and `<level>_code`, its P-code (ET04), taken from the lookup key the
registry stores (REGION_ET04). Filters and map joins use the code; charts label
with the name.
"""

import re

# The dashboards' levels, outermost first. Their names are the API's filter
# parameters and response keys.
LEVELS: tuple[str, ...] = ("region", "zone", "woreda", "kebele")

# Master Data ids carry the level ('region-ET04'), registry lookup keys an
# upper-case one ('REGION_ET04'); the P-code is what follows.
_LEVEL_PREFIX = re.compile(r"^[A-Za-z]+[-_]")


def code(value: str) -> str:
    """The P-code in a filter value: 'region-ET04', 'REGION_ET04' and 'ET04' all give 'ET04'."""
    return _LEVEL_PREFIX.sub("", value.strip())


def code_column(level: str) -> str:
    return f"{level}_code"


def name_column(level: str) -> str:
    return f"{level}_name"
