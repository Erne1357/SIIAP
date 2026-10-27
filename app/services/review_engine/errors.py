"""Business errors of the review engine (phase 6D). Messages are Spanish and user-facing."""
from app.services.errors import ConflictError, DomainError, NotFoundError


class ReviewError(DomainError):
    """Base of every review engine refusal (400 unless a subclass says otherwise)."""


class ReviewNotFound(ReviewError, NotFoundError):
    """Unknown kind or item, or an item outside the actor's program scope (404)."""


class ReviewConflict(ReviewError, ConflictError):
    """The decision clashes with the item's current state (409); nothing is written."""


class ReviewForbidden(ReviewError):
    """The actor lacks the decision permission of the kind (403)."""

    status_code = 403
    code = 'FORBIDDEN'
