from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, List, Tuple


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def load_swagger_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _deref_swagger2_schema(schema: Any, swagger: Dict[str, Any], *, _stack: Tuple[str, ...] = ()) -> Any:
    """
    Deref $ref вида '#/definitions/NAME' рекурсивно.
    - цикл -> {'type':'object','x-circular_ref': ref}
    - нерешённое -> {'x-unresolved_ref': ref}
    ВАЖНО: возвращает inline-объект (не оставляет '$ref' если ref решаемый).
    """
    defs = swagger.get("definitions", {}) or {}

    def resolve_ref(ref: str) -> Any:
        if not ref.startswith("#/definitions/"):
            return {"x-unresolved_ref": ref}
        name = ref.split("/", 2)[-1]
        if name not in defs:
            return {"x-unresolved_ref": ref}
        return defs[name]

    if isinstance(schema, list):
        return [_deref_swagger2_schema(x, swagger, _stack=_stack) for x in schema]

    if not isinstance(schema, dict):
        return schema

    if "$ref" in schema:
        ref = schema["$ref"]
        if ref in _stack:
            merged = {k: v for k, v in schema.items() if k != "$ref"}
            merged.setdefault("type", "object")
            merged["x-circular_ref"] = ref
            return _deref_swagger2_schema(merged, swagger, _stack=_stack)

        resolved = resolve_ref(ref)
        if isinstance(resolved, dict) and "x-unresolved_ref" in resolved:
            merged = {k: v for k, v in schema.items() if k != "$ref"}
            merged["x-unresolved_ref"] = ref
            return _deref_swagger2_schema(merged, swagger, _stack=_stack)

        base = deepcopy(resolved)
        local = {k: v for k, v in schema.items() if k != "$ref"}
        base.update(local)  # локальные поля приоритетнее
        return _deref_swagger2_schema(base, swagger, _stack=_stack + (ref,))

    # обычная рекурсия
    return {k: _deref_swagger2_schema(v, swagger, _stack=_stack) for k, v in schema.items()}


def _merge_parameters(path_params: List[Dict[str, Any]] | None,
                      op_params: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    """
    Объединяет параметры уровня path и операции.
    Дедуп: по (name, in).
    """
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for src in (path_params or []), (op_params or []):
        for p in src:
            if not isinstance(p, dict):
                continue
            key = (str(p.get("name", "")), str(p.get("in", "")))
            # при конфликте приоритет у параметра операции
            if key not in merged or src is (op_params or []):
                merged[key] = deepcopy(p)
    return list(merged.values())


def _extract_request_body_from_params(params: List[Dict[str, Any]], swagger: Dict[str, Any],
                                      unresolved: List[str]) -> Dict[str, Any] | None:
    """
    Swagger 2.0: тело — это parameter с in='body' и schema.
    Возвращаем объект фиксированной формы.
    """
    for p in params:
        if isinstance(p, dict) and p.get("in") == "body":
            schema = p.get("schema")
            if schema is None:
                body_schema = None
            else:
                body_schema = _deref_swagger2_schema(schema, swagger)
                # соберём unresolved refs
                _collect_unresolved_refs(body_schema, unresolved)
            return {
                "in": "body",
                "name": p.get("name", "body"),
                "required": bool(p.get("required", False)),
                "schema": body_schema,
                "description": p.get("description", None),
            }
    return None


def _deref_parameters(params: List[Dict[str, Any]], swagger: Dict[str, Any], unresolved: List[str]) -> None:
    for p in params:
        if not isinstance(p, dict):
            continue
        if "schema" in p:
            p["schema"] = _deref_swagger2_schema(p["schema"], swagger)
            _collect_unresolved_refs(p["schema"], unresolved)
        # formData/body/query params могут иметь items/properties и т.п. без schema
        # но в Swagger 2.0 это тоже schema-like структура внутри самого параметра:
        for k in ("items",):
            if k in p:
                p[k] = _deref_swagger2_schema(p[k], swagger)
                _collect_unresolved_refs(p[k], unresolved)


def _deref_responses(responses: Dict[str, Any], swagger: Dict[str, Any], unresolved: List[str]) -> None:
    for _, resp in (responses or {}).items():
        if not isinstance(resp, dict):
            continue
        if "schema" in resp:
            resp["schema"] = _deref_swagger2_schema(resp["schema"], swagger)
            _collect_unresolved_refs(resp["schema"], unresolved)


def _collect_unresolved_refs(node: Any, out: List[str]) -> None:
    """
    Собирает любые 'x-unresolved_ref' рекурсивно.
    """
    if isinstance(node, dict):
        if "x-unresolved_ref" in node and isinstance(node["x-unresolved_ref"], str):
            out.append(node["x-unresolved_ref"])
        for v in node.values():
            _collect_unresolved_refs(v, out)
    elif isinstance(node, list):
        for x in node:
            _collect_unresolved_refs(x, out)


def extract_endpoints_swagger2(swagger: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Возвращает массив endpoint-объектов в формате:
    {
      path, method, summary, description, parameters, request_body,
      responses, tags, operation_id, x_unresolved_refs
    }
    """
    if swagger.get("swagger") != "2.0":
        raise ValueError("This extractor supports Swagger 2.0 only (swagger: '2.0').")

    endpoints: List[Dict[str, Any]] = []
    paths = swagger.get("paths", {}) or {}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        path_level_params = path_item.get("parameters") if isinstance(path_item.get("parameters"), list) else []

        for method_lc, op in path_item.items():
            if method_lc not in HTTP_METHODS:
                continue
            if not isinstance(op, dict):
                continue

            unresolved: List[str] = []

            op_params = op.get("parameters") if isinstance(op.get("parameters"), list) else []
            parameters = _merge_parameters(path_level_params, op_params)

            # deref параметров
            _deref_parameters(parameters, swagger, unresolved)

            # request_body (из body-parameter)
            request_body = _extract_request_body_from_params(parameters, swagger, unresolved)

            # responses
            responses = deepcopy(op.get("responses", {}) or {})
            _deref_responses(responses, swagger, unresolved)

            endpoint_obj = {
                "path": path,
                "method": method_lc.upper(),
                "summary": op.get("summary", "") or "",
                "description": op.get("description", None),
                "parameters": parameters,
                "request_body": request_body,
                "responses": responses,
                "tags": op.get("tags", []) or [],
                "operation_id": op.get("operationId", None),
                "x_unresolved_refs": unresolved,
            }
            endpoints.append(endpoint_obj)

    return endpoints