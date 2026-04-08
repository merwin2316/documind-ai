"""
Transformation Agent - Reformats previous answers based on user commands.
Only reformats, never adds new information or changes topic.
"""
from typing import Optional
from openai import AsyncOpenAI
from config import settings


class TransformAgent:
    """Agent that transforms previous answers without changing content or topic."""
    
    def __init__(self):
        # Set timeout for OpenAI API calls (60 seconds for transformations)
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=60.0
        )
    
    async def transform(
        self,
        previous_answer: str,
        transformation_type: str,
        topic: str
    ) -> str:
        """
        Transform previous answer based on user command.
        
        Args:
            previous_answer: The previous assistant response
            transformation_type: "list" | "shorten" | "names_only"
            topic: Current topic (for topic locking)
        """
        system_prompt = """You are a response transformation agent.

Rules:
- Do NOT add new information
- Do NOT remove factual content
- Do NOT change topic
- ONLY reformat the previous answer

LIST FORMATTING RULES (CRITICAL):
- ONE item per bullet point
- Each bullet on its own line
- NO dash-separated inline lists (Movie A - Movie B - Movie C)
- NO explanations inside bullets
- Start with "- " followed by the item

❌ WRONG FORMAT:
- Movie A - Movie B - Movie C

✅ CORRECT FORMAT:
- Movie A
- Movie B
- Movie C

Allowed transformations:
- list → Extract enumerable items as bullet points (movies, names, steps, features)
- shorten → Make the response more concise while keeping key information
- names_only → Extract only names/items that can be listed

If the previous response has no listable items (e.g., pure description), respond:
"There is nothing to list from the previous response."

STYLE:
- Clean, readable formatting
- No explanations unless needed
- Preserve factual accuracy"""

        # Determine transformation instruction
        if transformation_type == "list":
            instruction = """Extract only factual items that can logically be listed from the previous response.
Examples of listable items: movie names, person names, steps, features, dates, locations.
If the previous response is a descriptive paragraph or explanation with no enumerable items, respond:
"There is nothing to list from the previous response."

CRITICAL FORMATTING RULES:
- Format as a clean bullet point list with ONE item per line
- NO dash-separated inline lists (Movie A - Movie B is WRONG)
- NO explanations, just clean bullets: "- Item name"
- Each item must be on its own line starting with "- "
- Example correct format:
  - Item 1
  - Item 2
  - Item 3"""
        elif transformation_type == "shorten":
            instruction = "Make the previous response shorter and more concise. Keep all key information."
        elif transformation_type == "names_only":
            instruction = """Extract only the names/items from the previous response that can be listed.
If no such items exist, respond: "There is nothing to list from the previous response."
Otherwise, use bullet points. No explanations."""
        else:
            instruction = "Reformat the previous response as requested, but only if it makes logical sense."

        user_prompt = f"""TOPIC: {topic}

PREVIOUS ASSISTANT RESPONSE:
{previous_answer}

USER INSTRUCTION:
{instruction}

Transform the previous response according to the instruction.
Do NOT add new information. Do NOT change topic. Do NOT convert descriptive paragraphs into bullets unless they contain enumerable items."""

        response = await self.openai_client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Low temperature for consistent transformations
            max_tokens=500
        )
        
        transformed = response.choices[0].message.content
        return self._sanitize_output(transformed)
    
    def _sanitize_output(self, text: str) -> str:
        """
        Robust sanitization - preserve ChatGPT's natural formatting.
        Normalize bullets and fix dash-separated inline lists.
        """
        import re
        
        # Trim outer whitespace
        result = text.strip()
        
        # Normalize bullet symbol ONLY (never touch markdown *)
        result = result.replace("• ", "- ")
        result = result.replace("▪ ", "- ")
        result = result.replace("▫ ", "- ")
        
        # CRITICAL FIX: Convert dash-separated inline lists to proper bullets
        # Pattern: "- Item A - Item B - Item C" → "- Item A\n- Item B\n- Item C"
        # Also handles: "Item A - Item B - Item C" (without leading dash)
        lines = result.split('\n')
        fixed_lines = []
        for line in lines:
            line_stripped = line.strip()
            
            # Case 1: Line starts with "- " and contains " - " (multiple items)
            if line_stripped.startswith('- ') and ' - ' in line_stripped:
                # Split by " - " but keep the first "- " intact
                parts = line_stripped.split(' - ')
                # First part already has "- ", rest need it added
                fixed_lines.append(parts[0])
                for part in parts[1:]:
                    part_cleaned = part.strip()
                    if part_cleaned:  # Skip empty parts
                        fixed_lines.append('- ' + part_cleaned)
            
            # Case 2: Line contains multiple " - " patterns but doesn't start with "- "
            # This catches cases like "Movie A - Movie B - Movie C" (no leading dash)
            elif ' - ' in line_stripped and not line_stripped.startswith('- '):
                # Check if it looks like a list (has multiple items separated by " - ")
                parts = line_stripped.split(' - ')
                if len(parts) >= 2:  # At least 2 items
                    # Check if parts are short (likely list items, not prose)
                    avg_length = sum(len(p.strip()) for p in parts) / len(parts)
                    if avg_length < 50:  # Likely a list, not prose
                        for part in parts:
                            part_cleaned = part.strip()
                            if part_cleaned:
                                fixed_lines.append('- ' + part_cleaned)
                    else:
                        # Probably prose with dashes, keep as is
                        fixed_lines.append(line)
                else:
                    fixed_lines.append(line)
            
            # Case 3: Line with multiple dashes in a row (e.g., "- Movie A - Movie B")
            # This is already handled by Case 1, but we add a regex pattern as backup
            elif re.search(r'^-\s+[^-]+(?:\s+-\s+[^-]+)+', line_stripped):
                # Pattern matches: "- word - word - word" (one or more repetitions)
                parts = re.split(r'\s+-\s+', line_stripped)
                if len(parts) >= 2:
                    # First part already has "- ", rest need it added
                    fixed_lines.append(parts[0] if parts[0].startswith('-') else '- ' + parts[0])
                    for part in parts[1:]:
                        part_cleaned = part.strip()
                        if part_cleaned:
                            fixed_lines.append('- ' + part_cleaned)
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        
        result = '\n'.join(fixed_lines)
        
        # Ensure bullets have a space after dash
        result = re.sub(r'(?m)^-\s*([^\s])', r'- \1', result)
        
        # Remove any trailing dashes or spaces from bullet items
        result = re.sub(r'(?m)^-\s+(.+?)\s*-\s*$', r'- \1', result)
        
        # Collapse excessive blank lines (keep paragraphs)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result
    
    def _classify_transformation_type(self, user_message: str) -> str:
        """Classify the type of transformation requested."""
        message_lower = user_message.lower()
        
        if "list" in message_lower or "show" in message_lower:
            return "list"
        if "short" in message_lower or "brief" in message_lower or "summarize" in message_lower:
            return "shorten"
        if "name" in message_lower or "only" in message_lower:
            return "names_only"
        
        return "list"  # Default to list

