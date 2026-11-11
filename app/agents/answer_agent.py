"""
Answer Agent — generates conversational answers using the configured LLM provider.
"""
import logging
import re
import time
from typing import Optional, AsyncIterator
from shared.llm.factory import get_llm_provider
from app.agents.response_formatter import format_list_response
from app.utils.tracer import trace, step

logger = logging.getLogger(__name__)


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

        model_name = getattr(self.llm, "chat_model", "ollama")
        context_len = len(context) if context else 0

        trace("AnswerAgent.generate_answer_stream ENTER",
              topic=topic,
              expected_format=expected_format,
              has_context=context is not None,
              context_len=context_len,
              question_len=len(question),
              system_prompt_len=len(system_prompt),
              user_prompt_len=len(user_prompt),
              model=model_name)

        start = time.perf_counter()
        chunk_count = 0
        full_response = []
        logger.info(
            "LLM START AnswerAgent.generate_answer_stream max_tokens=4000 question_len=%s context_len=%s",
            len(question),
            context_len,
        )
        try:
            async for chunk in self.llm.generate_stream(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            ):
                chunk_count += 1
                full_response.append(chunk)
                yield chunk
        except Exception as e:
            logger.exception(
                "LLM ERROR AnswerAgent.generate_answer_stream elapsed=%.2fs chunks=%s error=%s",
                time.perf_counter() - start,
                chunk_count,
                repr(e),
            )
            raise
        elapsed = time.perf_counter() - start
        raw = "".join(full_response)
        logger.info(
            "LLM END AnswerAgent.generate_answer_stream elapsed=%.2fs chunks=%s",
            elapsed,
            chunk_count,
        )
        trace("AnswerAgent.generate_answer_stream EXIT",
              elapsed_s=round(elapsed, 2),
              chunk_count=chunk_count,
              response_len=len(raw))

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

        model_name = getattr(self.llm, "chat_model", "ollama")
        context_len = len(context) if context else 0

        trace("AnswerAgent.generate_answer ENTER",
              question_len=len(question),
              context_len=context_len,
              user_prompt_len=len(user_prompt),
              model=model_name)

        start = time.perf_counter()
        logger.info(
            "LLM START AnswerAgent.generate_answer max_tokens=4000 question_len=%s context_len=%s",
            len(question),
            context_len,
        )
        try:
            answer = await self.llm.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            )
        except Exception as e:
            logger.exception(
                "LLM ERROR AnswerAgent.generate_answer elapsed=%.2fs error=%s",
                time.perf_counter() - start,
                repr(e),
            )
            raise
        elapsed = time.perf_counter() - start
        logger.info(
            "LLM END AnswerAgent.generate_answer elapsed=%.2fs response_len=%s",
            elapsed,
            len(answer),
        )
        trace("AnswerAgent.generate_answer EXIT",
              elapsed_s=round(elapsed, 2),
              response_len=len(answer))

        formatted = format_list_response(answer, expected_format)
        return self._sanitize_output(formatted)

    # ------------------------------------------------------------------ #
    # Prompts
    # ------------------------------------------------------------------ #
    def _build_system_prompt(self) -> str:
        return """You are DocuMind AI.

You will receive a DOCUMENT CONTEXT section containing text retrieved from uploaded documents.

RULES — follow these without exception:

1. If DOCUMENT CONTEXT is provided, answer ONLY using information from that context.
   Do NOT use outside knowledge when the context contains relevant information.

2. Never ignore the DOCUMENT CONTEXT. It is your primary and authoritative source.

3. If the answer cannot be found anywhere in the DOCUMENT CONTEXT, respond with:
   "The uploaded document does not contain information about that."
   Do NOT guess or fabricate an answer.

4. Every factual statement taken from the context MUST include its citation number immediately after the fact.
   Format: sentence text [N]
   Example: Machine Learning is a subset of Artificial Intelligence [1].

5. Never invent citations. Never cite a number that does not appear in the DOCUMENT CONTEXT.

6. Do not summarize using only the document file name. Quote or paraphrase actual content.

FORMATTING RULES:
- Tone: Professional and direct. Act like a knowledgeable senior mentor.
- Keep paragraphs short (max 2 lines). Add whitespace between sections.
- For lists of items/entities: use **Bold Term** followed by a description — not bullet points.
- Use bullet points only for simple enumerations (steps, features).
- Do NOT add a References section. Citations are inline only.
- Do NOT output empty citation markers like [].
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
            parts.append(
                f"""==========================
DOCUMENT CONTEXT
==========================

{context}

==========================
END DOCUMENT CONTEXT
=========================="""
            )
            parts.append(
                "IMPORTANT:\n"
                "The DOCUMENT CONTEXT above is your PRIMARY SOURCE.\n"
                "Base your answer ONLY on the content inside it.\n"
                "Do NOT use general knowledge if the answer exists in the context.\n"
                "Every factual sentence MUST end with its citation number [N]."
            )

        parts.append(f"USER QUESTION:\n{question}")

        is_greeting = topic.lower() == "greeting" or question.lower().strip() in ["hi", "hey", "hello"]
        if expected_format != "list" and not is_follow_up and not is_greeting:
            parts.append(
                "\nAt the END of your response, add:\n\n"
                "Want to explore more? You could ask:\n- Question 1?\n- Question 2?\n- Question 3?"
            )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------ #
    def _sanitize_output(self, text: str) -> str:
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
