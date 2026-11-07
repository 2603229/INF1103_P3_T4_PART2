# FILE GUIDE: AI failure exception used for absent credentials, network issues and unusable responses.
# The workflow catches this error and avoids persisting an unassessed report.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Exception raised when live AI assessment cannot be verified."""


# Signals AI failure, such as missing credentials or network downtime.
# The workflow converts this into a safe, user-visible submission failure.
class AssessmentUnavailable(RuntimeError):
    """The real AI response could not be verified; do not save an incident."""
