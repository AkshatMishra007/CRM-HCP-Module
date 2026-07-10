EXTRACTION_PROMPT = """
Extract the following information from the medical representative interaction.

Return ONLY valid JSON.

{
    "hcp_name": "",
    "hospital": "",
    "interaction_type": "",
    "interaction_date": "",
    "interaction_time": "",
    "meeting_location": "",
    "topics_discussed": "",
    "materials_shared": [],
    "samples_distributed": [],
    "sentiment": "Positive | Neutral | Negative",
    "outcomes": "Result of the meeting",
    "follow_up_actions": "Next action to perform"
}

Rules:

- interaction_date must be in YYYY-MM-DD format.
- interaction_time must be in 24-hour HH:MM format.
- If the date is not mentioned, return "".
- If the time is not mentioned, return "".
- Return ONLY valid JSON.

Sentiment Rules:

Choose ONLY one of these values:

- Positive
- Neutral
- Negative

Do NOT invent other values such as:
- interested
- strong interest
- happy
- satisfied
- excited

If the doctor showed interest, enthusiasm, willingness to prescribe, or requested more information, return:

"Positive"

If the doctor was undecided, return:

"Neutral"

If the doctor rejected the product or expressed dissatisfaction, return:

"Negative"

Outcome:
What was the result of the interaction?

Examples:
- Doctor showed interest in prescribing.
- Doctor requested clinical trial data.
- Doctor agreed to evaluate the product.
- Doctor declined the product.
- Doctor requested more samples.

Follow-up Action:
What should happen after the meeting?

Examples:
- Send clinical trial data.
- Schedule another meeting.
- Call next week.
- Send product brochure.
- Arrange product demonstration.

"""