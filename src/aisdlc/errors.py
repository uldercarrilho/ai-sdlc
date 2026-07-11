class AisdlcError(Exception):
    """Base error for aisdlc."""


class ValidationError(AisdlcError):
    """Schema or semantic validation failure."""


class ChainIntegrityError(AisdlcError):
    """Event chain hash or sequence integrity failure."""


class ArtifactMismatchError(AisdlcError):
    """Stored artifact bytes do not match declared digest."""
