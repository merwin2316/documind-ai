"""
Answer Agent — generates conversational answers using the configured LLM provider.
"""
from typing import Optional, AsyncIterator
from shared.llm.factory import get_llm_provider
from app.agents.response_formatter import format_list_response


class AnswerAgent:
    """Agent that generates natural, citation-backed answers."""

    def __init__(self):
        self.llm = get_llm_provider()

    async def generate_answer_stream(
        self,
        question: str,
        topic: str,
        expected_format: str,
        context: Optional[str] = None,
        previous_answer: Optional[str] = None,
        is_follow_up: bool = False,
        active_entity: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream a ChatGPT-style answer. Yields text chunks."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            question, topic, expected_format, context,
            previous_answer, is_follow_up, active_entity,
        )

        async for chunk in self.llm.generate_stream(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
        ):
            yield chunk

    async def generate_answer(
        self,
        question: str,
        topic: str,
        expected_format: str,
        context: Optional[str] = None,
        previous_answer: Optional[str] = None,
        is_follow_up: bool = False,
        active_entity: Optional[str] = None,
    ) -> str:
        """Generate a complete answer (non-streaming)."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            question, topic, expected_format, context,
            previous_answer, is_follow_up, active_entity,
        )

        answer = await self.llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
        )

        formatted = format_list_response(answer, expected_format)
        return self._sanitize_output(formatted)

    # ------------------------------------------------------------------ #
    # Prompts
    # ------------------------------------------------------------------ #
    def _build_system_prompt(self) -> str:
        return """### ROLE
You are DocuMind AI, an **objective, accurate, and practical AI assistant**.
Your role is to provide direct answers based strictly on facts from the provided documents, acting as a knowledgeable guide.

### CORE DIRECTIVES
1. **Objectivity & Accuracy**
   - Prioritize correctness above all else.
   - **Minimize Hallucinations**: If the answer isn't in the `DOCUMENT CONTEXT`, strictly state that you don't know based on the documents.
   - **Honesty**: Never provide misleading confidence.

2. **Critical Guidance**
   - If a user's question assumes incorrect premises based on the documents, correct them politely.
   - Proactively flag potential misunderstandings.

3. **Response Structure**
   - **Direct Answer**: Start with the direct answer/recommendation immediately.
   - **Reasoning**: Provide the "Why" or details (citing documents).
   - **Actionable Info**: Extract key steps or data points clearly.

### GUIDELINES

#### 1. Tone and Style ("Professional & Punchy")
- **Tone**: Collaborative and Professional. Act like a senior mentor.
- **Punchy**: Use short, clear sentences. Avoid fluff.
- **Direct**: Start answers immediately.

#### 2. Formatting Rules (Mandatory)
- **Paragraphs**: Keep them short (maximum 2 lines). Add whitespace.
- **Structure for Items/Entities**: Use **Paragraphs starting with Bold Terms**.
  - **Style**: `**Item Name** Description or explanation...`
- **Simple Lists**: Only use bullet points for simple lists of features or steps, not for the main answer entities.

#### 3. Citations (CRITICAL)
- **Mandatory**: You must verify facts against the `DOCUMENT CONTEXT`.
- **Inline**: Place citations `[N]` **immediately** after the fact they support.
  - YES: "Project Alpha [1] started in 2023 [2]."
  - NO: "Project Alpha started in 2023 [1][2]."

### CONSTRAINTS
- **DOCUMENT PRIORITY**: Always prioritize `DOCUMENT CONTEXT` for specific facts.
- **GENERAL KNOWLEDGE FALLBACK**: If details are NOT in the `DOCUMENT CONTEXT`:
  1. Clearly state: "The documents don't have specific details about [topic]."
  2. **THEN PROCEED** to provide a general answer based on your knowledge.
- **NO HALLUCINATION OF DOCS**: Do NOT claim general knowledge comes from the documents.
- Do not output empty citation markers `[]`.
- **NO BARE LISTS**: Write full, conversational sentences.
- **NO "References" Section**: Citations are inline only.
"""

    def _build_user_prompt(
        self, question, topic, expected_format, context,
        previous_answer, is_follow_up, active_entity,
    ) -> str:
        parts = [f"TOPIC: {topic}", f"EXPECTED FORMAT: {expected_format}"]

        if expected_format == "list":
            parts.append("FORMAT: Use **Paragraphs starting with Bold Terms**.")
            parts.append("CRITICAL: Do NOT use bullet points (-) for the main items.")
            parts.append("MANDATORY: EVERY item MUST have an explanation.")

        if active_entity:
            parts.append(f"ACTIVE ENTITY: {active_entity}")
            parts.append("Resolve all pronouns to refer to the ACTIVE ENTITY.")

        if previous_answer:
            label = "PREVIOUS ANSWER" if is_follow_up else "PREVIOUS ANSWER (for context)"
            parts.append(f"{label}:\n{previous_answer}")

        if context:
            parts.append(f'DOCUMENT CONTEXT:\n"""\n{context}\n"""')
            parts.append("\nUse relevant facts from the DOCUMENT CONTEXT and cite them with [N].")

        parts.append(f"USER QUESTION:\n{question}")
        parts.append("\nAnswer in a natural, conversational way.")

        is_greeting = topic.lower() == "greeting" or question.lower().strip() in ["hi", "hey", "hello"]
        if expected_format != "list" and not is_follow_up and not is_greeting:
            parts.append(
                "\nAt the END of your response, add:\n\n"
                "Want to explore more? You could ask:\n- Question 1?\n- Question 2?\n- Question 3?"
            )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------ #
    def _sanitize_output(self, text: str) -> str:
        import re
        result = text.strip()
        result = result.replace("• ", "- ").replace("▪ ", "- ").replace("▫ ", "- ")

        lines = result.split("\n")
        fixed = []
        for line in lines:
            s = line.strip()
            is_def = re.match(r"^- \*\*.+?\*\* - ", s)
            if s.startswith("- ") and " - " in s and not is_def:
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
