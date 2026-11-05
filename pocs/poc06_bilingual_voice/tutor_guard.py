"""Reject empty POC-03 provider output before POC-05 records a conversation turn."""
from __future__ import annotations


class EmptyTutorResponseError(RuntimeError):
    pass


class NonEmptyTutor:
    """Transparent guard around POC-03 Tutor; all state and prompting stay in the original Tutor."""

    def __init__(self, tutor):
        self._tutor = tutor
        self.last_failure: str | None = None

    def ask(self, prompt: str) -> str:
        self.last_failure = None
        response = self._tutor.ask(prompt)
        if not isinstance(response, str) or not response.strip():
            self.last_failure = "empty_response"
            raise EmptyTutorResponseError("Tutor returned no text; speech was not generated.")
        return response

    def __getattr__(self, name: str):
        return getattr(self._tutor, name)

