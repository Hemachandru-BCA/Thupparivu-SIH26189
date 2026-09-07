"""
_compat.py
-----------
All models in this package are written against the real **pydantic v2** API
(`BaseModel`, `Field`, `field_validator`). In this sandboxed environment
`pydantic` cannot be pip-installed (no network access), so this module
provides a minimal drop-in fallback that supports the subset of the API this
project uses (field defaults + single-field "after" validators).

In production simply `pip install pydantic` (see requirements.txt) and the
real library is imported automatically -- no application code changes needed.
"""

try:
    from pydantic import BaseModel, Field, field_validator, ValidationError  # noqa: F401
    PYDANTIC_AVAILABLE = True

except ImportError:  # pragma: no cover - exercised only when pydantic missing
    PYDANTIC_AVAILABLE = False

    class ValidationError(Exception):
        pass

    class _FieldInfo:
        def __init__(self, default=None, default_factory=None, description=None):
            self.default = default
            self.default_factory = default_factory
            self.description = description

    def Field(default=None, default_factory=None, description=None, **kwargs):
        return _FieldInfo(default=default, default_factory=default_factory, description=description)

    def field_validator(*fields, mode="after"):
        """Registers a function as a validator for one or more fields."""
        def decorator(func):
            target = func.__func__ if isinstance(func, classmethod) else func
            target._is_field_validator = True
            target._validated_fields = fields
            return classmethod(target) if not isinstance(func, classmethod) else func
        return decorator

    class BaseModel:
        def __init__(self, **data):
            annotations = {}
            for klass in reversed(type(self).__mro__):
                annotations.update(getattr(klass, "__annotations__", {}))

            for name in annotations:
                if name in data:
                    setattr(self, name, data[name])
                    continue
                default = getattr(type(self), name, None)
                if isinstance(default, _FieldInfo):
                    if default.default_factory is not None:
                        setattr(self, name, default.default_factory())
                    else:
                        setattr(self, name, default.default)
                elif default is not None or hasattr(type(self), name):
                    setattr(self, name, default)
                else:
                    raise ValidationError(f"Missing required field: {name}")

            self._run_validators(annotations)

        def _run_validators(self, annotations):
            for klass in type(self).__mro__:
                for attr_name, attr in vars(klass).items():
                    func = attr.__func__ if isinstance(attr, classmethod) else attr
                    if callable(func) and getattr(func, "_is_field_validator", False):
                        for field_name in func._validated_fields:
                            if field_name in annotations:
                                current = getattr(self, field_name)
                                setattr(self, field_name, func(type(self), current))

        def dict(self):
            return {k: getattr(self, k) for k in self.__annotations_flat()}

        def model_dump(self):
            return self.dict()

        def __annotations_flat(self):
            annotations = {}
            for klass in reversed(type(self).__mro__):
                annotations.update(getattr(klass, "__annotations__", {}))
            return annotations

        def __repr__(self):
            fields = ", ".join(f"{k}={v!r}" for k, v in self.dict().items())
            return f"{type(self).__name__}({fields})"
