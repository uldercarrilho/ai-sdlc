import aisdlc
from aisdlc.errors import ValidationError


def test_package_imports():
    assert hasattr(aisdlc, "__version__")


def test_validation_error_is_exception():
    assert issubclass(ValidationError, Exception)
