from __future__ import annotations

from typing import Any


def _normalize_binary_field(schema: Any) -> None:
    if isinstance(schema, dict):
        is_binary_string = schema.get("type") == "string" and (
            "contentMediaType" in schema or schema.get("contentEncoding") == "binary"
        )
        if is_binary_string:
            schema.pop("contentMediaType", None)
            schema.pop("contentEncoding", None)
            schema["format"] = "binary"

        for value in schema.values():
            _normalize_binary_field(value)

    elif isinstance(schema, list):
        for item in schema:
            _normalize_binary_field(item)


def normalize_binary_upload_schema(openapi_schema: dict[str, Any]) -> dict[str, Any]:
    paths = openapi_schema.get("paths", {})
    components = openapi_schema.get("components", {}).get("schemas", {})

    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue

        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue

            multipart_schema = (
                operation.get("requestBody", {})
                .get("content", {})
                .get("multipart/form-data", {})
                .get("schema")
            )
            if not multipart_schema:
                continue

            _normalize_binary_field(multipart_schema)

            schema_ref = multipart_schema.get("$ref")
            if schema_ref:
                schema_name = schema_ref.rsplit("/", 1)[-1]
                component_schema = components.get(schema_name)
                if component_schema:
                    _normalize_binary_field(component_schema)

    return openapi_schema
