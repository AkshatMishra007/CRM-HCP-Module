import json
import re


def parse_json(response: str):
    """
    Extract JSON from an LLM response.
    Works even if the model wraps JSON in markdown.
    """

    try:
        return json.loads(response)

    except json.JSONDecodeError:

        match = re.search(r"\{.*\}", response, re.DOTALL)

        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return {}

        return {}