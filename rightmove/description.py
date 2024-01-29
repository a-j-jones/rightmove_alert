import json
import logging
import os
from typing import Dict

import openai

from config import DATA
from config.logging import logging_setup

with open(os.path.join(DATA, "secrets.json"), "r") as f:
    secrets = json.load(f)

key = secrets.get("openai").get("api_key")
openai.api_key = key

logger = logging.getLogger(__name__)
logger = logging_setup(logger)

TOOLS = [{
    "type": "function",
    "function": {
        "name": "property_assessment",
        "description": "Record structured data about a property.",
        "parameters": {
            "type": "object",
            "properties": {
                "garden": {
                    "type": "string",
                    "enum": ["private", "communal", "balcony", "unknown"],
                    "description": (
                        "The type of garden the property has, if known. For example"
                        " - If the property has a private garden or patio, the value would be 'private'."
                        " - If the property has a communal garden, the value would be 'communal'."
                        " - If the property has a private balcony, the value would be 'balcony'."
                    ),
                }
            },
            "required": ["garden"],
        },
    },
}]


def analyse_summary(summary: str) -> Dict:

    prompt = f"""
    # PROMPT:
    Please review the following property summary and determine the additional metadata using the included tool.
    
    ```
    {summary}
    ```
    """

    messages = [
        {
            "role": "system",
            "content": (
                "You are a property analyst and your job is to review property summaries and provide structured data."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    chat_response = openai.ChatCompletion.create(model="gpt-3.5-turbo-1106", messages=messages, tools=TOOLS)

    output = json.loads(chat_response.choices[0].message.tool_calls[0].function.to_dict()["arguments"])

    return output
