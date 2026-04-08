"""
Answer Agent — generates ChatGPT-style conversational answers.
Uses knowledge + optional document context with inline citations.
"""
from typing import Optional
from openai import AsyncOpenAI
from config import settings
from app.agents.response_formatter import format_list_response


class AnswerAgent:
    """Agent that generates natural, citation-backed answers."""
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=120.0
        )
    
    async def generate_answer_stream(
        self,
        question: str,
        topic: str,
        expected_format: str,
        context: Optional[str] = None,
        previous_answer: Optional[str] = None,
        is_follow_up: bool = False,
        active_entity: Optional[str] = None
    ):
        """
        Stream a ChatGPT-style answer. Yields text chunks as generated.
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            question, topic, expected_format, context, 
            previous_answer, is_follow_up, active_entity
        )
        
        stream = await self.openai_client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=4000,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the answer agent."""
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
- **Engaging**: Use light emojis (max 2-3) where appropriate (e.g., 🚀, 💡).

#### 2. Formatting Rules (Mandatory)
- **Paragraphs**: Keep them short (maximum 2 lines). Add whitespace.
- **Structure for Items/Entities**: Do NOT use bullet points for the main entities. Use **Paragraphs starting with Bold Terms**.
  1. **Style**: `**Item Name** Description or explanation...`
  2. **Example**:
     ```
     **Netflix** is a global streaming giant known for its wide reach [1].

     **Amazon Prime Video** offers a vast platform for films [2].
     ```
- **Simple Lists**: Only use bullet points for simple lists of features or steps, not for the main answer entities.

#### 3. Citations (CRITICAL)
- **Mandatory**: You must verify facts against the `DOCUMENT CONTEXT`.
- **Inline**: Place citations `[N]` **immediately** after the fact they support.
  - YES: "Project Alpha [1] started in 2023 [2]."
  - NO: "Project Alpha started in 2023 [1][2]."

#### 4. Examples
**User**: "What is the budget?"
**Output**:
"The budget is **$50,000** assigned for Q1 [1].

**Reasoning:**
This allocation focuses on marketing and initial development [2]. It was approved directly by the board [1]."

### CONSTRAINTS
- **DOCUMENT PRIORITY**: Always prioritize `DOCUMENT CONTEXT` for specific facts.
- **GENERAL KNOWLEDGE FALLBACK**: If the user asks about specific details and they are NOT in the `DOCUMENT CONTEXT`:
  1. Clearly state: "The documents don't have specific details about [topic]."
  2. **THEN PROCEED** to provide a general answer or recommendation based on your general knowledge.
- **NO HALLUCINATION OF DOCS**: Do NOT claim the general knowledge comes from the documents.
- Do not output empty citation markers `[]`.
- **NO BARE LISTS**: Do NOT just list entities. ALWAYS write full, conversational sentences.
- **NO "References" Section**: Do NOT include a "References" or "Sources" list at the end. Citations are inline only.
"""

    def _build_user_prompt(
        self,
        question: str,
        topic: str,
        expected_format: str,
        context: Optional[str] = None,
        previous_answer: Optional[str] = None,
        is_follow_up: bool = False,
        active_entity: Optional[str] = None
    ) -> str:
        """Build the user prompt based on arguments."""
        user_parts = [
            f"TOPIC: {topic}",
            f"EXPECTED FORMAT: {expected_format}"
        ]
        
        if expected_format == "list":
            user_parts.append("FORMAT: Use **Paragraphs starting with Bold Terms** (`**Item** Description`).")
            user_parts.append("Example: '**Netflix** is a global streaming platform...'")
            user_parts.append("CRITICAL: Do NOT use bullet points (-) for the main items. Use separate paragraphs.")
            user_parts.append("MANDATORY: EVERY item MUST have an explanation.")
        
        if active_entity:
            user_parts.append(f"ACTIVE ENTITY: {active_entity}")
            user_parts.append("Resolve all pronouns (he, she, they, him, her, it) to refer to the ACTIVE ENTITY.")
        
        if previous_answer:
            if is_follow_up:
                user_parts.append(f"PREVIOUS ANSWER:\n{previous_answer}")
                user_parts.append("STRICT RULE: Do not restate who the person is. Only extract or list what is asked.")
            else:
                user_parts.append(f"PREVIOUS ANSWER (for context — enhance/enrich if requested):\n{previous_answer}")
                user_parts.append("The user may be asking to enhance the previous answer. Use your knowledge to add requested information.")
        
        if context:
            user_parts.append(f'DOCUMENT CONTEXT:\n"""\n{context}\n"""')
            user_parts.append("\n📌 Citation Instructions:")
            user_parts.append("Use ANY relevant facts from the DOCUMENT CONTEXT and cite them immediately with [N].")
        
        user_parts.append(f"USER QUESTION:\n{question}")
        user_parts.append("\nAnswer in a natural, conversational way. Keep it friendly, clear, and easy to read.")
        
        # Suggestion prompts for non-list, non-follow-up, non-greeting queries
        is_greeting = topic.lower() == "greeting" or question.lower().strip() in ["hi", "hey", "hello"]
        if expected_format != "list" and not is_follow_up and not is_greeting:
            user_parts.append("\nIMPORTANT: At the very END of your response, add:\n\nWant to explore more? You could ask:\n- Question 1?\n- Question 2?\n- Question 3?")
        
        return "\n\n".join(user_parts)

    async def generate_answer(
        self,
        question: str,
        topic: str,
        expected_format: str,
        context: Optional[str] = None,
        previous_answer: Optional[str] = None,
        is_follow_up: bool = False,
        active_entity: Optional[str] = None
    ) -> str:
        """Generate a natural ChatGPT-style answer (non-streaming)."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            question, topic, expected_format, context, 
            previous_answer, is_follow_up, active_entity
        )
        
        response = await self.openai_client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        answer = response.choices[0].message.content
        formatted_answer = format_list_response(answer, expected_format)
        return self._sanitize_output(formatted_answer)
    
    def _sanitize_output(self, text: str) -> str:
        """Normalize bullet characters and fix inline list formatting."""
        import re
        
        result = text.strip()
        
        # Normalize bullet symbols
        result = result.replace("• ", "- ")
        result = result.replace("▪ ", "- ")
        result = result.replace("▫ ", "- ")
        
        # Fix dash-separated inline lists → proper bullet lists
        lines = result.split('\n')
        fixed_lines = []
        for line in lines:
            line_stripped = line.strip()
            
            # Protect defined items like "- **Name** - Explanation"
            is_defined_item = re.match(r'^- \*\*.+?\*\* - ', line_stripped)
            if line_stripped.startswith('- ') and ' - ' in line_stripped and not is_defined_item:
                parts = line_stripped.split(' - ')
                fixed_lines.append(parts[0])
                for part in parts[1:]:
                    part_cleaned = part.strip()
                    if part_cleaned:
                        fixed_lines.append('- ' + part_cleaned)
            elif ' - ' in line_stripped and not line_stripped.startswith('- '):
                parts = line_stripped.split(' - ')
                if len(parts) >= 2:
                    avg_length = sum(len(p.strip()) for p in parts) / len(parts)
                    if avg_length < 50:
                        for part in parts:
                            part_cleaned = part.strip()
                            if part_cleaned:
                                fixed_lines.append('- ' + part_cleaned)
                    else:
                        fixed_lines.append(line)
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        
        result = '\n'.join(fixed_lines)
        result = re.sub(r'(?m)^-\s*([^\s])', r'- \1', result)
        result = re.sub(r'(?m)^-\s+(.+?)\s*-\s*$', r'- \1', result)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result
