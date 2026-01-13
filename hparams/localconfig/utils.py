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
    Parse a type hint string into a tuple of (base_types, is_optional, inner_type).

    Examples:
        'int' -> ([int], False, None)
        'Optional[int]' -> ([int], True, None)
        'int | None' -> ([int], True, None)
        'int | str' -> ([int, str], False, None)
        'int | str | None' -> ([int, str], True, None)
        'list[int]' -> ([list], False, int)
        'Optional[list[str]]' -> ([list], True, str)

    Returns:
        (base_types, is_optional, inner_type) where:
        - base_types: List of allowed Python types
        - is_optional: Whether None is allowed
        - inner_type: For generic types like list[int], the inner type
    """
    type_str = type_str.strip()
    is_optional = False
    inner_type = None

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

        return (base_types, is_optional, inner_type)

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

        # Parse inner type (simplified - just take first type for list)
        inner_parts = inner_str.split(',')
        inner_name = inner_parts[0].strip()
        inner_type = TYPE_MAP.get(inner_name.lower())

        return ([base_type], is_optional, inner_type)

    # Simple type
    base_type = TYPE_MAP.get(type_str.lower())
    if base_type is None:
        raise TypeError(f"Unknown type: {type_str}")

    return ([base_type], is_optional, inner_type)


def validate_type(value: Any, type_hint: str) -> bool:
    """
    Validate that a value matches the declared type hint.

    Args:
        value: The Python value to validate
        type_hint: The type hint string (e.g., 'int', 'Optional[str]', 'list[int]', 'int | str')

    Returns:
        True if value matches the type hint

    Raises:
        TypeError: If value doesn't match the declared type
    """
    base_types, is_optional, inner_type = parse_type_hint(type_hint)

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

    # Check inner type for lists
    if inner_type is not None and matched_type == list:
        for i, item in enumerate(value):
            if not isinstance(item, inner_type):
                # Allow int items in float lists
                if inner_type == float and isinstance(item, int):
                    continue
                raise TypeError(
                    f"List item at index {i} expected {inner_type.__name__}, "
                    f"got {type(item).__name__} (value: {repr(item)})"
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
    base_types, is_optional, inner_type = parse_type_hint(type_hint)

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
