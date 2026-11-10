# FILE GUIDE: Custom exception for AI assessment failures.
# Used when credentials are missing, API requests fail,
# or Gemini does not return a valid assessment.

"""Define the exception raised when AI assessment is unavailable."""


# Signals AI failure, such as missing credentials or network downtime.
# The workflow converts this into a safe, user-visible submission failure.
class AssessmentUnavailable(RuntimeError):
    """Indicate that a valid AI assessment could not be obtained.

    Raised when AI processing cannot produce a verified result,
    such as during API connection failures, missing credentials,
    invalid responses, or unsupported image evidence.

    The application workflow should handle this exception safely
    and prevent unassessed reports from being saved.
    """