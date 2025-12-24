"""Test services package marker for absolute imports in pytest.

This file exists to ensure `services` is recognized as a Python package so
imports like `from services.conftest import validate_schema` work during test
collection and execution.
"""


