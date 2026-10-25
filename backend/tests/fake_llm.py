"""A stand-in for LLMClient: answers "extract_requirements" from a fixture table, never calls an API."""

import json
from pathlib import Path

from app.ai.llm import LLMClient, LLMError

ANSWERS = Path(__file__).parent / "fixtures" / "llm" / "extract_answers.json"


class FakeLLM(LLMClient):
    """For every sentence that contains a `match` text of the table, returns that entry's requirements.

    `fail_on_call=n` raises LLMError on the n-th call (1-based); `extra` items are added to every answer.
    """

    def __init__(self, fail_on_call: int | None = None, extra: list[dict] | None = None):
        self.table = json.loads(ANSWERS.read_text(encoding="utf-8"))
        self.fail_on_call = fail_on_call
        self.extra = extra or []
        self.calls: list[dict] = []

    def complete_json(self, prompt_name, variables, schema):
        assert prompt_name == "extract_requirements"
        self.calls.append(variables)
        if self.fail_on_call == len(self.calls):
            raise LLMError("The AI returned an invalid answer twice. Try again.")
        found = []
        for message in variables["batch"]:
            for sentence in message["sentences"]:
                for entry in self.table:
                    if entry["match"] in sentence["text"]:
                        found += [{**r, "sentence_ids": [sentence["id"]]} for r in entry["requirements"]]
        return schema.model_validate({"requirements": found + self.extra})

    @property
    def sentences_sent(self) -> list[str]:
        return [s["text"] for call in self.calls for m in call["batch"] for s in m["sentences"]]
