class DomainError(Exception):
    """Base exception for domain-level validation failures."""


class InvalidMemoryError(DomainError):
    """Raised when a memory violates domain rules."""


class MemoryNotFoundError(DomainError):
    """Raised when a requested memory does not exist."""


class InvalidStateTransitionError(DomainError):
    """Raised when a memory lifecycle transition is not allowed."""


class AmbiguousContradictionError(DomainError):
    """Raised when conflicting information cannot be safely reconciled."""