"""
Intent & Format Agent — classifies user intent and determines formatting.
Outputs JSON only, no natural language.
"""
import json
from typing import Dict, Optional
from shared.llm.factory import get_llm_provider


class IntentAgent:
    """Agent that classifies user intent and determines formatting requirements."""

    def __init__(self):
        self.llm = get_llm_provider()

    async def classify(
        self,
        user_message: str,
        previous_topic: Optional[str] = None,
        previous_active_entity: Optional[str] = None,
        previous_message: Optional[str] = None,
    ) -> Dict:
        """Classify user intent and return structured JSON."""

        system_prompt = """You are an intent classification agent for a document intelligence assistant.

Your job is to analyze the user's message and return a STRICT JSON object.

Rules:
- Output JSON only. No explanations, no markdown, no extra text.

You must determine:
1. intent: "content_query" | "document_vault" | "follow_up"
2. topic: string describing the topic
3. active_entity: main entity/person/subject being discussed
4. is_follow_up: true only for FORMAT-ONLY transformation of previous output
5. expected_format: "paragraph" | "list" | "mixed"
6. needs_documents: true if the question asks for content that might be in uploaded files

Definitions:
- "content_query" — searching for CONTENT within documents or general knowledge
- "document_vault" — asking to LIST files or check FILENAMES (metadata only)
- "follow_up" — formatting/transformation of previous answer (e.g. "list them", "shorten")

active_entity rules:
- If user mentions a named entity, extract it
- If user uses pronouns (he, she, they, it), resolve from previous_active_entity or previous_message
- NEVER leave active_entity empty when pronouns are used

is_follow_up rules:
- true ONLY if message is a FORMAT transformation (e.g., "list them", "shorten", "only names")
- Content queries like "tell me more", "expand", "give summary" are NOT follow-ups

needs_documents rules:
- true for content queries about features, requirements, details, summaries, tech stack, etc.
- false for pure greetings, formatting transformations, vault queries, small talk
- DEFAULT: if in doubt, set true

Return JSON:
{
  "intent": "content_query",
  "topic": "...",
  "active_entity": "...",
  "is_follow_up": false,
  "expected_format": "paragraph",
  "needs_documents": true
}"""

        # Build user prompt
        parts = ["USER MESSAGE:", user_message, ""]
        if previous_topic:
            parts.append(f"PREVIOUS TOPIC: {previous_topic}")
        if previous_active_entity:
            parts.append(f"PREVIOUS ACTIVE ENTITY: {previous_active_entity}")
        if previous_message:
            parts.append(f"PREVIOUS ASSISTANT MESSAGE:\n{previous_message}")
        parts.extend([
            "",
            "Analyze the message and return JSON only.",
            "Resolve pronouns using context above.",
        ])

        user_prompt = "\n".join(parts)

        print("=" * 100)
        print(system_prompt)
        print("=" * 100)
        print(user_prompt)
        print("=" * 100)
        
        print("=" * 100)
        print(system_prompt)    
        print("=" * 100)
        print(user_prompt)
        print("=" * 100)
        response = await self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=200,
            json_mode=True,
        )

        result_json = json.loads(response)

        # Validate required fields
        defaults = {
            "intent": "content_query",
            "topic": "general",
            "active_entity": previous_active_entity or "general",
            "is_follow_up": False,
            "expected_format": "paragraph",
            "needs_documents": False,
        }
        for key, default in defaults.items():
            if key not in result_json:
                result_json[key] = default

        return result_json
