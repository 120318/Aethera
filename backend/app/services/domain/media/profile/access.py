from __future__ import annotations


def model_field_value(model, field: str, default=None):
    data = model.__dict__ if model else {}
    return data[field] if field in data else default


def model_field_list(model, field: str) -> list:
    value = model_field_value(model, field, [])
    return list(value or [])
