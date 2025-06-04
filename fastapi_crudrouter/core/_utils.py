"""Patch for fastapi-crudrouter to work with Pydantic v2"""
from typing import Optional, Type, Any, Dict, List, get_type_hints

from fastapi import Depends, HTTPException
from pydantic import create_model

from ._types import T, PAGINATION, PYDANTIC_SCHEMA


class AttrDict(dict):  # type: ignore
    def __init__(self, *args, **kwargs) -> None:  # type: ignore
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


def get_pk_type(schema: Type["BaseModel"], pk_field: str) -> type:
    """
    Get the type of the primary key field for Pydantic v2 compatibility
    """
    # Get model fields - Pydantic v2 compatible way
    model_fields = schema.model_fields if hasattr(schema, "model_fields") else {}

    # Try to get the field from model_fields (Pydantic v2)
    if model_fields and pk_field in model_fields:
        # Get type annotation from model fields
        field_info = model_fields[pk_field]
        # Get annotation
        return field_info.annotation

    # Fallback to type hints
    type_hints = get_type_hints(schema)
    if pk_field in type_hints:
        return type_hints[pk_field]

    # Default to int if we can't determine
    return int


def schema_factory(
    schema_cls: Type[T], pk_field_name: str = "id", name: str = "Create"
) -> Type[T]:
    """
    Is used to create a CreateSchema which does not contain pk
    """
    fields = {}
    
    # Handle Pydantic v2
    if hasattr(schema_cls, "model_fields"):
        fields = {
            field_name: (field_info.annotation, ...)
            for field_name, field_info in schema_cls.model_fields.items()
            if field_name != pk_field_name
        }
    # Fallback to Pydantic v1
    elif hasattr(schema_cls, "__fields__"):
        fields = {
            f.name: (f.type_, ...)
            for f in schema_cls.__fields__.values()
            if f.name != pk_field_name
        }
    
    name = schema_cls.__name__ + name
    
    # Handle different create_model signatures between Pydantic v1 and v2
    try:
        # Try Pydantic v2 signature first
        schema: Type[T] = create_model(name, **fields)  # type: ignore
    except TypeError:
        # Fall back to Pydantic v1 signature
        schema: Type[T] = create_model(__model_name=name, **fields)  # type: ignore

    return schema

def create_query_validation_exception(field: str, msg: str) -> HTTPException:
    return HTTPException(
        422,
        detail={
            "detail": [
                {"loc": ["query", field], "msg": msg, "type": "type_error.integer"}
            ]
        },
    )


def pagination_factory(max_limit: Optional[int] = None) -> Any:
    """
    Created the pagination dependency to be used in the router
    """

    def pagination(skip: int = 0, limit: Optional[int] = max_limit) -> PAGINATION:
        if skip < 0:
            raise create_query_validation_exception(
                field="skip",
                msg="skip query parameter must be greater or equal to zero",
            )

        if limit is not None:
            if limit <= 0:
                raise create_query_validation_exception(
                    field="limit", msg="limit query parameter must be greater then zero"
                )

            elif max_limit and max_limit < limit:
                raise create_query_validation_exception(
                    field="limit",
                    msg=f"limit query parameter must be less then {max_limit}",
                )

        return {"skip": skip, "limit": limit}

    return Depends(pagination)
