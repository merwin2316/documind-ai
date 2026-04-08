"""
Intent & Format Agent - Classifies user intent and determines formatting.
Outputs JSON only, no natural language.
"""
import json
from typing import Dict, Optional
from openai import AsyncOpenAI
from config import settings


class IntentAgent:
    """Agent that classifies user intent and determines formatting requirements."""
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=60.0
        )
    
    async def classify(
        self,
        user_message: str,
        previous_topic: Optional[str] = None,
        previous_active_entity: Optional[str] = None,
        previous_message: Optional[str] = None
    ) -> Dict:
        """
        Classify user intent and return structured JSON.
        
        Returns:
            {
                "intent": "content_query" | "document_vault" | "follow_up",
                "topic": str,
                "active_entity": str,
                "is_follow_up": bool,
                "expected_format": "paragraph" | "list" | "mixed",
                "needs_documents": bool
            }
        """
        system_prompt = """You are an intent classification agent for a document intelligence assistant.

Your job is to analyze the user's message and return a STRICT JSON object.

Rules:
- Output JSON only
- No explanations
- No markdown
- No extra text

You must determine:
1. intent
2. topic
3. active_entity
4. is_follow_up
5. expected_format
6. needs_documents

Definitions:
- intent:
  - "content_query" - searching for CONTENT within documents, general knowledge, or specific details
  - "document_vault" - asking to LIST files or check specific FILENAMES (metadata only)
  - "follow_up" - formatting or transformation of previous answer

- active_entity:
  - The main entity/person/subject being discussed
  - Used for pronoun resolution (he, she, they, it, him, her)
  - Extraction priority:
    1. If user mentions a named entity -> extract it directly
    2. If user uses pronouns:
       - If previous_active_entity exists -> use it
       - If previous_active_entity is NOT provided but previous_message exists -> extract the main entity from previous_message
       - NEVER leave active_entity empty when pronouns are used
  - If no entity can be determined, use the topic as active_entity

- is_follow_up:
  - true ONLY if the message refers to previous assistant output for FORMAT-ONLY transformation
  - Examples of follow-ups: "list them", "shorten", "only names", "make it points"
  - Must have BOTH:
    1. Transformation verb (list, shorten, make, convert, format)
    2. Reference to previous output (them, those, these, it, that, this)
  - NOT follow-ups (these are new content queries):
    * "give summary of it" - new content query
    * "tell me about it" - new content query
    * "explain it" - new content query
  - Content enhancement keywords (NOT follow-ups): "with year", "add year", "more details", "expand", "elaborate"

CONVERSATIONAL COREFERENCE RULES (CRITICAL):
- If the user uses pronouns (he, she, they, him, her, it):
  1. If previous_active_entity is provided -> use it directly
  2. If previous_active_entity is NOT provided BUT previous_message exists:
     - You MUST extract the main subject/person/entity from previous_message.
     - Look for the primary subject discussed in the assistant's last answer.
     - If the previous message discusses a specific project, tool, or document, SET active_entity to that name.
     - Examples: extract person names, project names, document titles, etc.
  3. NEVER return active_entity as empty, null, or "general" when pronouns are used
  4. NEVER mark as ambiguous or ask for clarification
  5. Mark is_follow_up = false (unless it's a transformation command like "list them")
  6. A question that adds new information about the same entity is NOT a follow-up

- expected_format:
  - "paragraph" - for who/what/why explanations
  - "list" - for movies, names, steps, rankings
  - "mixed" - for explanations with examples

Formatting rules:
- If user asks for movies, names, steps, rankings -> "list"
- If user asks who/what/why -> "paragraph"
- If user asks explanation + examples -> "mixed"

Topic locking:
- If is_follow_up is true, topic MUST remain unchanged from previous_topic.
- If previous_topic is provided and message doesn't change subject, use previous_topic.
- Otherwise, infer topic from the message.

Documents:
- needs_documents = true if the question asks for CONTENT that might be in uploaded files.
- **AGGRESSIVE RETRIEVAL**: If the user asks for "features", "requirements", "details", "summary", etc., set needs_documents = true.
- **TECHNICAL QUERIES**: If the user asks about "structure", "architecture", "tech stack", etc., set needs_documents = true.
- **ENHANCEMENT QUERIES**: If the user asks to "expand", "elaborate", "tell me more", set needs_documents = true.
- **IMPLICIT CONTEXT**: If the user asks a question that implies a specific subject and a previous_active_entity can be inferred, set needs_documents = true.
- Examples of needs_documents = true: 
  * "features of the project"
  * "give 10 points"
  * "requirements for X"
  * "what is [X]"
  * "summary of [document]"
  * "search for [name]"
  * "project structure"
  * "tech stack used"
- Only set to false for:
  * Pure greetings ("hi", "hello")
  * Pure formatting transformations ("make it short", "list them")
  * Explicit vault queries ("list my files", "what files do i have")
  * General small talk clearly unrelated to work intent
- **DEFAULT RULE**: If in doubt, set needs_documents = true.

Formatting Rules:
- If query asks for "details", "context", "summary", "expand" -> "paragraph"
- If query asks for "list", "bullet points", "names", "steps" -> "list"
- If query asks for "comparison", "pros and cons" -> "mixed"

Return JSON only in this format:
{
  "intent": "content_query" | "document_vault" | "follow_up",
  "topic": "string describing the topic",
  "active_entity": "string describing the active entity/person/subject",
  "is_follow_up": true | false,
  "expected_format": "paragraph" | "list" | "mixed",
  "needs_documents": true | false
}"""

        # Build user prompt parts
        user_parts = ["USER MESSAGE:", user_message, ""]
        
        if previous_topic:
            user_parts.append(f"PREVIOUS TOPIC: {previous_topic}")
        
        if previous_active_entity:
            user_parts.append(f"PREVIOUS ACTIVE ENTITY: {previous_active_entity}")
        
        if previous_message:
            user_parts.append(f"PREVIOUS ASSISTANT MESSAGE (for context):\n{previous_message}")
        
        user_parts.extend([
            "",
            "Analyze the message and return JSON only.",
            "Resolve pronouns using previous_active_entity if provided.",
            "If previous_active_entity is not provided but previous_message exists, infer the active entity from the previous message context.",
            "If the user uses pronouns (he, she, they, him, her, it), resolve them to the active entity from the conversation context."
        ])
        
        user_prompt = "\n".join(user_parts)

        response = await self.openai_client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        
        result_json = json.loads(response.choices[0].message.content)
        
        # Validate and ensure all required fields exist
        required_fields = ["intent", "topic", "active_entity", "is_follow_up", "expected_format", "needs_documents"]
        for field in required_fields:
            if field not in result_json:
                if field == "intent":
                    result_json[field] = "content_query"
                elif field == "topic":
                    result_json[field] = "general"
                elif field == "active_entity":
                    if previous_active_entity:
                        result_json[field] = previous_active_entity
                    else:
                        result_json[field] = result_json.get("topic", "general")
                elif field == "is_follow_up":
                    result_json[field] = False
                elif field == "expected_format":
                    result_json[field] = "paragraph"
                elif field == "needs_documents":
                    result_json[field] = False
        
        return result_json
