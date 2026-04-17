class DomainError(Exception):
    """Base domain exception."""


class NotFoundError(DomainError):
    """Raised when an entity is not found."""


class ConflictError(DomainError):
    """Raised when an entity conflicts with existing data."""
