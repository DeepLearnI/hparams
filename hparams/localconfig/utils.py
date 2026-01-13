import re
from typing import Any, Optional, Type, Union, get_origin, get_args

# Matches: key = value (original format)
CONFIG_KEY_RE = re.compile(r'[A-Za-z0-9\-\_\.]+\s*=')

# Matches: key: type = value (type-annotated format)
# Captures: (key, type_hint, value)
# Supports: int, Optional[int], list[int], int | str | None
CONFIG_KEY_TYPE_RE = re.compile(
    r'^([A-Za-z0-9\-\_\.]+)\s*:\s*([A-Za-z0-9_\[\],\s\|]+)\s*=\s*(.*)$'
)

# Supported type names mapping to Python types
TYPE_MAP = {
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'list': list,
    'dict': dict,
    'none': type(None),
    'None': type(None),
}


def is_float(value):
    """ Checks if the value is a float """
    return _is_type(value, float)


def is_int(value):
    """ Checks if the value is an int """
    return _is_type(value, int)


def is_bool(value):
    """ Checks if the value is a bool """
    return value.lower() in ['true', 'false', 'yes', 'no', 'on', 'off']


def is_none(value):
    """ Checks if the value is a None """
    return value.lower() == str(None).lower()


def to_bool(value):
    """ Converts value to a bool """
    return value.lower() in ['true', 'yes', 'on']


def is_config(value):
    """ Checks if the value is possible config content """
    return '\n' in value or CONFIG_KEY_RE.match(value)


def _is_type(value, type):
    try:
        type(value)
        return True
    except Exception:
        return False


def parse_type_hint(type_str: str) -> tuple:
    """
    Parse a type hint string into a tuple of (base_types, is_optional, inner_types).

    Examples:
        'int' -> ([int], False, None)
        'Optional[int]' -> ([int], True, None)
        'int | None' -> ([int], True, None)
        'int | str' -> ([int, str], False, None)
        'int | str | None' -> ([int, str], True, None)
        'list[int]' -> ([list], False, (int,))
        'dict[str, int]' -> ([dict], False, (str, int))
        'Optional[list[str]]' -> ([list], True, (str,))

    Returns:
        (base_types, is_optional, inner_types) where:
        - base_types: List of allowed Python types
        - is_optional: Whether None is allowed
        - inner_types: Tuple of inner types for generics (e.g., (int,) for list[int], (str, int) for dict[str, int])
    """
    type_str = type_str.strip()
    is_optional = False
    inner_types = None

    # Handle pipe union syntax: int | str | None
    if '|' in type_str:
        parts = [p.strip() for p in type_str.split('|')]
        base_types = []

        for part in parts:
            if part.lower() == 'none':
                is_optional = True
            else:
                t = TYPE_MAP.get(part.lower())
                if t is None:
                    raise TypeError(f"Unknown type: {part}")
                base_types.append(t)

        if not base_types:
            raise TypeError(f"Union type must have at least one non-None type: {type_str}")

        return (base_types, is_optional, inner_types)

    # Handle Optional[X]
    if type_str.startswith('Optional[') and type_str.endswith(']'):
        is_optional = True
        type_str = type_str[9:-1].strip()

    # Handle generic types like list[int], dict[str, int]
    if '[' in type_str:
        base_name = type_str[:type_str.index('[')]
        inner_str = type_str[type_str.index('[') + 1:-1].strip()

        base_type = TYPE_MAP.get(base_name.lower())
        if base_type is None:
            raise TypeError(f"Unknown type: {base_name}")

        # Parse inner types
        inner_parts = [p.strip() for p in inner_str.split(',')]
        inner_types = tuple(
            TYPE_MAP.get(p.lower()) for p in inner_parts
        )

        # Validate all inner types are known
        for i, (part, typ) in enumerate(zip(inner_parts, inner_types)):
            if typ is None:
                raise TypeError(f"Unknown inner type: {part}")

        return ([base_type], is_optional, inner_types)

    # Simple type
    base_type = TYPE_MAP.get(type_str.lower())
    if base_type is None:
        raise TypeError(f"Unknown type: {type_str}")

    return ([base_type], is_optional, inner_types)


def validate_type(value: Any, type_hint: str) -> bool:
    """
    Validate that a value matches the declared type hint.

    Args:
        value: The Python value to validate
        type_hint: The type hint string (e.g., 'int', 'Optional[str]', 'list[int]', 'dict[str, int]')

    Returns:
        True if value matches the type hint

    Raises:
        TypeError: If value doesn't match the declared type
    """
    base_types, is_optional, inner_types = parse_type_hint(type_hint)

    # Handle None values
    if value is None:
        if is_optional:
            return True
        raise TypeError(f"Value is None but type '{type_hint}' is not Optional")

    # Check if value matches any of the allowed base types
    type_matched = False
    matched_type = None

    for base_type in base_types:
        # Special handling: int is also valid for float type hints
        if base_type == float and isinstance(value, (int, float)):
            type_matched = True
            matched_type = base_type
            break
        elif isinstance(value, base_type):
            type_matched = True
            matched_type = base_type
            break

    if not type_matched:
        type_names = ' | '.join(t.__name__ for t in base_types)
        raise TypeError(
            f"Expected {type_names}, got {type(value).__name__} "
            f"(value: {repr(value)})"
        )

    # Check inner types for lists
    if inner_types is not None and matched_type == list:
        item_type = inner_types[0]
        for i, item in enumerate(value):
            if not isinstance(item, item_type):
                # Allow int items in float lists
                if item_type == float and isinstance(item, int):
                    continue
                raise TypeError(
                    f"List item at index {i} expected {item_type.__name__}, "
                    f"got {type(item).__name__} (value: {repr(item)})"
                )

    # Check inner types for dicts
    if inner_types is not None and matched_type == dict:
        key_type = inner_types[0] if len(inner_types) > 0 else None
        value_type = inner_types[1] if len(inner_types) > 1 else None

        for k, v in value.items():
            if key_type is not None and not isinstance(k, key_type):
                raise TypeError(
                    f"Dict key expected {key_type.__name__}, "
                    f"got {type(k).__name__} (key: {repr(k)})"
                )
            if value_type is not None and not isinstance(v, value_type):
                # Allow int values in float dicts
                if value_type == float and isinstance(v, int):
                    continue
                raise TypeError(
                    f"Dict value for key {repr(k)} expected {value_type.__name__}, "
                    f"got {type(v).__name__} (value: {repr(v)})"
                )

    return True


def coerce_to_type(value: Any, type_hint: str) -> Any:
    """
    Attempt to coerce a value to match the declared type hint.

    Args:
        value: The value to coerce
        type_hint: The type hint string

    Returns:
        The coerced value

    Raises:
        TypeError: If coercion is not possible
    """
    base_types, is_optional, inner_types = parse_type_hint(type_hint)

    # Handle None
    if value is None:
        if is_optional:
            return None
        raise TypeError(f"Cannot coerce None to non-optional type '{type_hint}'")

    # Check if already correct type
    for base_type in base_types:
        if isinstance(value, base_type):
            return value

    # Try coercion to first type in union
    base_type = base_types[0]

    # Special case: int to float
    if base_type == float and isinstance(value, int):
        return float(value)

    # Special case: bool strings
    if base_type == bool and isinstance(value, str):
        if is_bool(value):
            return to_bool(value)

    # Try direct conversion
    try:
        return base_type(value)
    except (ValueError, TypeError) as e:
        raise TypeError(
            f"Cannot coerce {type(value).__name__} to {type_hint}: {e}"
        )
