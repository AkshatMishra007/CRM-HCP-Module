from typing import Optional


def summarize_interaction(text: str) -> dict:
    return {
        "summary": text.strip(),
        "sentiment": "neutral",
    }
