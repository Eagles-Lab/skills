"""Public error types and CLI exit codes."""

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    INTERNAL_ERROR = 1
    INPUT_ERROR = 2
    PARTIAL_BATCH_FAILURE = 3
    PDF_EXTRACTION_ERROR = 4
    OUTPUT_ERROR = 5


class AnalyzerError(Exception):
    """Base error for expected analyzer failures."""


class InputValidationError(AnalyzerError):
    """The canonical resume input is invalid."""


class SourceMappingAuditError(InputValidationError):
    """Raw source evidence and canonical facts are materially inconsistent."""


class PDFExtractionError(AnalyzerError):
    """PDF text extraction failed or produced unusable text."""


class OutputSafetyError(AnalyzerError):
    """The requested output would be unsafe or ambiguous."""


class OutputConflictError(OutputSafetyError):
    """An output bundle already exists and overwrite was not requested."""
