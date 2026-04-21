"""
Transformation Agent — reformats previous answers based on user commands.
Only reformats, never adds new information.
"""
import re
from shared.llm.factory import get_llm_provider


class TransformAgent:
    """Agent that transforms previous answers without changing content."""

    def __init__(self):
        self.llm = get_llm_provider()

    async def transform(self, previous_answer: str, transformation_type: str, topic: str) -> str:
        """Transform previous answer based on user command."""

        system_prompt = """You are a response transformation agent.

Rules:
- Do NOT add new information
- Do NOT remove factual content
- Do NOT change topic
- ONLY reformat the previous answer

LIST FORMATTING RULES (CRITICAL):
- ONE item per bullet point. Each on its own line.
- NO dash-separated inline lists (Movie A - Movie B - Movie C)
- Start with "- " followed by the item

Allowed transformations:
- list → Extract enumerable items as bullet points
- shorten → Make the response more concise
- names_only → Extract only names/items

If the previous response has no listable items, respond:
"There is nothing to list from the previous response."
"""

        instructions = {
            "list": (
                "Extract factual items that can be listed. "
                "Format as clean bullet points: one item per line starting with '- '."
            ),
            "shorten": "Make the previous response shorter and more concise. Keep all key info.",
            "names_only": (
                "Extract only the names/items from the previous response. "
                "Use bullet points. No explanations."
            ),
        }
        instruction = instructions.get(transformation_type, "Reformat as requested.")

        user_prompt = f"""TOPIC: {topic}

PREVIOUS ASSISTANT RESPONSE:
{previous_answer}

USER INSTRUCTION:
{instruction}

Transform the previous response. Do NOT add new information."""

        response = await self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        return self._sanitize_output(response)

    def _classify_transformation_type(self, user_message: str) -> str:
        msg = user_message.lower()
        if "list" in msg or "show" in msg:
            return "list"
        if any(w in msg for w in ("short", "brief", "summarize")):
            return "shorten"
        if "name" in msg or "only" in msg:
            return "names_only"
        return "list"

    def _sanitize_output(self, text: str) -> str:
        result = text.strip()
        result = result.replace("\u2022 ", "- ").replace("\u25aa ", "- ").replace("\u25ab ", "- ")

        lines = result.split("\n")
        fixed = []
        for line in lines:
            s = line.strip()
            if s.startswith("- ") and " - " in s:
                parts = s.split(" - ")
                fixed.append(parts[0])
                fixed.extend(f"- {p.strip()}" for p in parts[1:] if p.strip())
            elif " - " in s and not s.startswith("- "):
                parts = s.split(" - ")
                if len(parts) >= 2 and sum(len(p) for p in parts) / len(parts) < 50:
                    fixed.extend(f"- {p.strip()}" for p in parts if p.strip())
                else:
                    fixed.append(line)
            else:
                fixed.append(line)

        result = "\n".join(fixed)
        result = re.sub(r"(?m)^-\s*([^\s])", r"- \1", result)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result
