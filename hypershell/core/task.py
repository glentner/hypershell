# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Hyper-shell task execution and formatting."""


RAW = '{}'
TEMPLATE = '{}'


def format_cmd(task_arg: str, template: str = TEMPLATE) -> str:
    """Format an command-lines."""
    return template.replace(RAW, task_arg)
