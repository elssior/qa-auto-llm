from __future__ import annotations

import importlib
import pkgutil
from typing import Optional
from pydantic_ai import Agent

def register_all(agent: Agent, package: str = "tools") -> None:
    pkg = importlib.import_module(package)

    # импортируем все подпакеты/модули внутри tools/*
    for m in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        mod = importlib.import_module(m.name)
        reg = getattr(mod, "register", None)
        if callable(reg):
            reg(agent)
