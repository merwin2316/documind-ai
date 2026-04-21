"""
RAG service for question answering with citations.
Orchestrates multiple agents: Intent, Answer, and Transform.
"""
from typing import List, Dict, Optional
from app.services.vector_store import VectorStore
from app.database.supabase_client import get_supabase_client
from app.agents.intent_agent import IntentAgent
from app.agents.answer_agent import AnswerAgent
from app.agents.transform_agent import TransformAgent
from config import settings


class RAGService:
    """Service for RAG-based question answering using multi-agent architecture."""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.intent_agent = IntentAgent()
        self.answer_agent = AnswerAgent()
        self.transform_agent = TransformAgent()
    
    def _is_simple_greeting(self, question: str) -> bool:
        """
        Detect if user message is a simple greeting or unclear prompt.
        
        Returns True for:
        - Simple greetings: "hi", "hey", "hello", "hey there", etc.
        - Very short unclear messages: "?", "what", "help", etc.
        - Empty or near-empty messages
        """
        question_lower = question.lower().strip()
        
        # Very short messages (1-3 words)
        words = question_lower.split()
        if len(words) <= 3:
            # Common greetings
            greetings = ["hi", "hey", "hello", "hey there", "hi there", "hello there", 
                        "what's up", "what up", "sup", "yo", "greetings", "good morning",
                        "good afternoon", "good evening", "howdy"]
            if question_lower in greetings or any(greeting in question_lower for greeting in greetings):
                return True
            
            # Unclear prompts
            unclear = ["?", "what", "help", "ok", "okay", "sure", "yes", "yeah", "yep", "no", "nope"]
            if question_lower in unclear:
                return True
        
        return False
    
    def _is_follow_up_command(self, question: str) -> bool:
        """
        Detect if user message is a follow-up/transformation command.
        
        Follow-up commands must:
        1. Be SHORT (≤4 words)
        2. Start with a transformation verb (list, show, shorten, etc.)
        3. Reference previous content (them, those, these, it, that)
        
        This prevents legitimate questions like "list the films he acted" 
        from being incorrectly treated as follow-ups.
        """
        question_lower = question.lower().strip()
        words = question_lower.split()
        
        # Must be very short (≤4 words) to be a follow-up
        if len(words) > 4:
            return False
        
        # Transformation verbs (must be first word or very early)
        transformation_verbs = [
            "list", "show", "shorten", "summarize", "convert", 
            "format", "make", "give"
        ]
        
        # Reference words (must be present)
        reference_words = [
            "them", "those", "these", "it", "that", "this"
        ]
        
        # Check if transformation verb is the first word (most common pattern)
        has_verb = any(words[0] == verb for verb in transformation_verbs) if words else False
        
        # Check if any reference word exists in the question
        has_reference = any(ref in words for ref in reference_words)
        
        # Follow-up ONLY if: has transformation verb AND has reference word AND is short
        return has_verb and has_reference
    
    def _classify_transformation_type(self, question: str) -> str:
        """
        Classify transformation type from follow-up command.
        
        Returns: "list" | "bullets" | "shorten" | "names_only" | "unknown"
        """
        question_lower = question.lower()
        
        if "list" in question_lower or "show" in question_lower:
            return "list"
        if "bullet" in question_lower or "point" in question_lower:
            return "bullets"
        if "short" in question_lower or "brief" in question_lower or "summarize" in question_lower:
            return "shorten"
        if "name" in question_lower or "only" in question_lower:
            return "names_only"
        
        return "list"  # Default to list
    
    async def answer_question(
        self,
        question: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        previous_message: Optional[str] = None,
        previous_topic: Optional[str] = None,
        previous_active_entity: Optional[str] = None
    ) -> Dict:
        """
        Answer a question using multi-agent RAG orchestration.
        
        Flow:
        1. Intent Agent → Classify intent, topic, format, follow-up, document needs, active_entity
        2. If document_vault → Answer about documents
        3. If follow_up → Transform Agent
        4. If needs_documents → Retrieve documents
        5. Answer Agent → Generate answer
        
        Args:
            question: User's question
            user_id: User ID for filtering documents
            document_ids: Optional list of document IDs to search within
            previous_message: Previous assistant message (for follow-ups)
            previous_topic: Previous topic (for topic locking)
            previous_active_entity: Previous active entity (for pronoun resolution)
        
        Returns:
            {
                "answer": str,
                "citations": List[Citation],
                "topic": str,  # Current topic for tracking
                "active_entity": str  # Current active entity for tracking
            }
        """
        # Step 1: Intent & Format Agent (MOST IMPORTANT)
        intent_result = await self.intent_agent.classify(
            user_message=question,
            previous_topic=previous_topic,
            previous_active_entity=previous_active_entity,
            previous_message=previous_message
        )
        
        intent = intent_result.get("intent", "content_query")
        topic = intent_result.get("topic", "general")
        active_entity = intent_result.get("active_entity", topic)  # Default to topic if not set
        is_follow_up = intent_result.get("is_follow_up", False)
        expected_format = intent_result.get("expected_format", "paragraph")
        needs_documents = intent_result.get("needs_documents", False)
        
        # Step 2: Handle simple greetings - return document list
        if self._is_simple_greeting(question):
            user_documents = await self._get_user_documents(user_id)
            if user_documents:
                document_names = [doc.get("name", "Unknown") for doc in user_documents]
                answer = f"Hey there! 😄\n\nHere are the documents available in your system:\n\n" + "\n".join([f"- {name}" for name in document_names])
            else:
                answer = "Hey there! 😄\n\nYou don't have any documents uploaded yet. Upload PDF documents to get started!"
            return {
                "answer": answer,
                "citations": [],
                "topic": "greeting",
                "active_entity": "general"
            }
        
        # Step 3: Handle document vault queries
        if intent == "document_vault":
            user_documents = await self._get_user_documents(user_id)
            answer = await self._answer_about_document_vault(question, user_documents)
            return {
                "answer": answer,
                "citations": [],
                "topic": topic,
                "active_entity": active_entity
            }
        
        # Step 4: Handle follow-up transformations
        if is_follow_up and previous_message:
            transformation_type = self._classify_transformation_type(question)
            answer = await self.transform_agent.transform(
                previous_answer=previous_message,
                transformation_type=transformation_type,
                topic=topic if topic else previous_topic or "general"
            )
            return {
                "answer": answer,
                "citations": [],
                "topic": topic if topic else previous_topic or "general",
                "active_entity": active_entity if active_entity else previous_active_entity or topic
            }
        
        # Step 5: Document Retrieval (ONLY if needed)
        context = ""
        chunks = []
        document_names = {}
        citations = []
        
        if needs_documents:
            # Context Injection: Use active_entity to improve search relevance
            # e.g. if active_entity is "ProjectX" and user asks "what is the tech stack",
            # we search for "ProjectX what is the tech stack"
            search_query = question
            if active_entity and active_entity.lower() != "general":
                 # Only prepend if entity isn't already in the question
                if active_entity.lower() not in question.lower():
                    search_query = f"{active_entity} {question}"
            
            chunks = await self.vector_store.search(
                query=search_query,
                user_id=user_id,
                top_k=settings.TOP_K_RETRIEVAL,
                document_ids=document_ids
            )
            
            if chunks:
                # Context Window Retrieval: Fetch neighbors for better context
                chunks = await self._fetch_neighbor_chunks(chunks)
                document_names = await self._get_document_names([chunk["document_id"] for chunk in chunks])
                context = self._build_context_with_citations(chunks, document_names)
        
        # Step 6: Answer Agent (ChatGPT-style generation)
        # Pass previous_answer if available (for content enhancement requests like "with year")
        # Answer Agent will use it if needed, even if is_follow_up=False
        # CRITICAL: If context exists, citations are MANDATORY
        answer = await self.answer_agent.generate_answer(
            question=question,
            topic=topic,
            expected_format=expected_format,
            context=context if context else None,
            previous_answer=previous_message if previous_message else None,
            is_follow_up=is_follow_up,
            active_entity=active_entity
        )
        
        # Post-process: If context was provided but no citations found, warn
        if context and chunks:
            citation_references = self._extract_citation_references(answer)
            if not citation_references:
                # Log warning but don't modify answer (let LLM learn from feedback)
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Document context was provided but no citations found in answer. Question: {question[:100]}")
        
        # Step 7: Extract and map citations (only if documents were used)
        return {
            "answer": answer,
            "citations": citations,
            "topic": topic,
            "active_entity": active_entity
        }

    async def answer_question_stream(
        self,
        question: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        previous_message: Optional[str] = None,
        previous_topic: Optional[str] = None,
        previous_active_entity: Optional[str] = None
    ):
        """
        Stream version of answer_question. Yields dict events.
        Events:
        - {"type": "status", "content": "Analyzing..."}
        - {"type": "token", "content": "The"}
        - {"type": "result", "data": {...}} (final result)
        """
        # Step 1: Intent & Format
        yield {"type": "status", "content": "Analyzing request..."}
        intent_result = await self.intent_agent.classify(
            user_message=question,
            previous_topic=previous_topic,
            previous_active_entity=previous_active_entity,
            previous_message=previous_message
        )
        
        intent = intent_result.get("intent", "content_query")
        topic = intent_result.get("topic", "general")
        active_entity = intent_result.get("active_entity", topic)
        is_follow_up = intent_result.get("is_follow_up", False)
        expected_format = intent_result.get("expected_format", "paragraph")
        needs_documents = intent_result.get("needs_documents", False)
        
        # Step 2: Simple Greetings
        if self._is_simple_greeting(question):
            yield {"type": "status", "content": "Responding..."}
            user_documents = await self._get_user_documents(user_id)
            if user_documents:
                document_names = [doc.get("name", "Unknown") for doc in user_documents]
                answer = f"Hey there! 😄\n\nHere are the documents available in your system:\n\n" + "\n".join([f"- {name}" for name in document_names])
            else:
                answer = "Hey there! 😄\n\nYou don't have any documents uploaded yet. Upload PDF documents to get started!"
                
            yield {"type": "token", "content": answer}
            yield {
                "type": "result", 
                "data": {
                    "answer": answer,
                    "citations": [],
                    "topic": "greeting",
                    "active_entity": "general"
                }
            }
            return

        # Step 3: Document Vault
        if intent == "document_vault":
            yield {"type": "status", "content": "Checking vault..."}
            user_documents = await self._get_user_documents(user_id)
            answer = await self._answer_about_document_vault(question, user_documents)
            
            yield {"type": "token", "content": answer}
            yield {
                "type": "result",
                "data": {
                    "answer": answer,
                    "citations": [],
                    "topic": topic,
                    "active_entity": active_entity
                }
            }
            return

        # Step 4: Follow-up Transformation
        if is_follow_up and previous_message:
            yield {"type": "status", "content": "Transforming answer..."}
            transformation_type = self._classify_transformation_type(question)
            answer = await self.transform_agent.transform(
                previous_answer=previous_message,
                transformation_type=transformation_type,
                topic=topic if topic else previous_topic or "general"
            )
            
            yield {"type": "token", "content": answer}
            yield {
                "type": "result",
                "data": {
                    "answer": answer,
                    "citations": [],
                    "topic": topic if topic else previous_topic or "general",
                    "active_entity": active_entity if active_entity else previous_active_entity or topic
                }
            }
            return

        # Step 5: Retrieval
        context = ""
        chunks = []
        document_names = {}
        
        if needs_documents:
            yield {"type": "status", "content": "Searching documents..."}
            
            # Context Injection: Use active_entity to improve search relevance
            search_query = question
            if active_entity and active_entity.lower() != "general":
                # Only prepend if entity isn't already in the question
                if active_entity.lower() not in question.lower():
                    search_query = f"{active_entity} {question}"
            
            chunks = await self.vector_store.search(
                query=search_query,
                user_id=user_id,
                top_k=settings.TOP_K_RETRIEVAL,
                document_ids=document_ids
            )
            
            if chunks:
                chunks = await self._fetch_neighbor_chunks(chunks)
                document_names = await self._get_document_names([chunk["document_id"] for chunk in chunks])
                context = self._build_context_with_citations(chunks, document_names)

        # Step 6: Generate Stream
        yield {"type": "status", "content": "Generating answer..."}
        
        full_answer = ""
        async for token in self.answer_agent.generate_answer_stream(
            question=question,
            topic=topic,
            expected_format=expected_format,
            context=context if context else None,
            previous_answer=previous_message if previous_message else None,
            is_follow_up=is_follow_up,
            active_entity=active_entity
        ):
            full_answer += token
            yield {"type": "token", "content": token}
        
        # Step 7: Citations
        citations = []
        if chunks and document_names:
            full_answer, citations = self._renumber_and_map_citations(full_answer, chunks, document_names)
            
        yield {
            "type": "result",
            "data": {
                "answer": full_answer,
                "citations": citations,
                "topic": topic,
                "active_entity": active_entity
            }
        }
    
    def _classify_transformation_type(self, question: str) -> str:
        """
        Classify transformation type from follow-up command.
        
        Returns: "list" | "shorten" | "names_only"
        """
        question_lower = question.lower()
        
        if "list" in question_lower or "show" in question_lower:
            return "list"
        if "short" in question_lower or "brief" in question_lower or "summarize" in question_lower:
            return "shorten"
        if "name" in question_lower or "only" in question_lower:
            return "names_only"
        
        return "list"  # Default to list
    
    def _extract_citation_references(self, answer: str) -> List[int]:
        """Extract citation IDs from answer text. Supports [N], 📄[N], and [CITATION N] formats."""
        import re
        # Try standard format first: [1], [2], etc. (most common)
        citation_ids = [int(match) for match in re.findall(r'\[(\d+)\]', answer)]
        # Fallback to emoji format: 📄[1], 📄[2], etc.
        if not citation_ids:
            citation_ids = [int(match) for match in re.findall(r'📄\[(\d+)\]', answer)]
        # Fallback to old format for backward compatibility
        if not citation_ids:
            citation_ids = [int(match) for match in re.findall(r'\[CITATION (\d+)\]', answer)]
        return citation_ids
    
    def _build_context_with_citations(
        self,
        chunks: List[Dict],
        document_names: Dict[str, str]
    ) -> str:
        """
        Build context string with citation markers.
        Uses [N] format to instruct LLM to use inline citations.
        """
        context_parts = []
        
        for idx, chunk in enumerate(chunks, start=1):
            doc_name = document_names.get(chunk["document_id"], "Unknown Document")
            # Use [N] format in context to guide LLM citation behavior (standard format)
            citation_text = f"[{idx}] {doc_name}, Page {chunk['page']}\nText: {chunk['text']}\n"
            context_parts.append(citation_text)
        
        return "\n".join(context_parts)
    
    def _determine_format_style(self, question: str) -> str:
        """
        Determine formatting style before calling LLM.
        Returns: "list" or "paragraph"
        """
        question_lower = question.lower()
        
        # Check for list indicators
        list_indicators = [
            "list", "top", "best", "highest", "give me", "show me",
            "top 5", "top 10", "top 20", "top 3", "top 7"
        ]
        
        # Check for ranking words
        ranking_words = ["top", "best", "highest", "most", "greatest"]
        
        # If contains list/ranking indicators, use list format
        if any(indicator in question_lower for indicator in list_indicators):
            return "list"
        
        # Default to paragraph
        return "paragraph"
    
    async def _transform_previous_answer(self, previous_answer: str, transformation_type: str) -> str:
        """
        Transform previous assistant answer based on user command.
        
        Examples:
        - "list them" → convert to bullet list
        - "shorten" → make shorter
        - "names only" → extract only names
        """
        # Pre-sanitize previous answer to normalize separators and formatting
        previous_answer = self._sanitize_output(previous_answer)
        
        # Use the same system prompt as main generation (consistent behavior)
        system_prompt = """You are a conversational AI assistant that behaves like ChatGPT.

CORE BEHAVIOR:
- Always understand the user's intent before formatting.
- Use your own knowledge as the primary source.
- Use document context only as optional hints.
- Never blindly reformat text without understanding meaning.

FORMATTING RULES:
- Use paragraphs for explanations and descriptions.
- Use bullet points ONLY for naturally enumerable items
  (movies, names, steps, features, rankings).
- Never convert descriptive paragraphs into bullets.
- Mixing paragraphs + bullets is encouraged when natural.

FOLLOW-UP RULES:
- Only treat very short commands like:
  "list them", "shorten this", "names only"
  as follow-up transformations.
- Follow-up commands MUST reference previous content.
- If a user restates a subject ("films he acted"),
  generate a NEW answer instead of transforming.

DOCUMENT RULES:
- Use document context silently.
- Never mention documents unless explicitly asked.
- If documents do not contain the answer, use general knowledge confidently.

STYLE:
- Friendly, clean, human-like responses 😊
- Clear spacing, readable formatting
- Optional 1–2 emojis per response"""

        # Build transformation instruction based on type
        if transformation_type == "list" or transformation_type == "bullets":
            user_instruction = """Extract only factual items that can logically be listed from the previous response.
Examples of listable items: movie names, person names, steps, features, dates, locations.
If the previous response is a descriptive paragraph or explanation with no enumerable items, respond:
"There is nothing to list from the previous response."

If items exist, format them as a clean bullet point list (one item per line). No explanations."""
        elif transformation_type == "shorten":
            user_instruction = "Make the previous response shorter and more concise. Keep the key information."
        elif transformation_type == "names_only":
            user_instruction = """Extract only the names/items from the previous response that can be listed.
If no such items exist, respond: "There is nothing to list from the previous response."
Otherwise, use bullet points. No explanations."""
        else:
            user_instruction = "Reformat the previous response as requested by the user, but only if it makes logical sense to do so."
        
        user_prompt = f"""PREVIOUS ASSISTANT RESPONSE:
{previous_answer}

USER INSTRUCTION:
{user_instruction}

Transform the previous response according to the user instruction.
Do not add new information. Do not convert descriptive paragraphs into bullets unless they contain enumerable items."""

        from shared.llm.factory import get_llm_provider
        llm = get_llm_provider()
        transformed = await llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=500,
        )
        return self._sanitize_output(transformed)
    
    def _sanitize_output(self, text: str) -> str:
        """
        Minimal formatting cleanup:
        - Normalize bullets (• to -)
        - Keep original line structure (don't force double newlines)
        - Just strip excessive whitespace
        """
        # Normalize bullet characters
        result = text.replace("•", "-")
        
        # Strip excessive whitespace at start/end
        result = result.strip()
        
        # Collapse multiple consecutive empty lines to max 2 (preserve paragraph breaks)
        import re
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result
    
    async def _generate_answer(
        self,
        question: str,
        context: str,
        has_context: bool = True
    ) -> tuple[str, List[int]]:
        """
        Generate answer using the configured LLM provider with citation requirements.
        
        Returns:
            (answer_text, list_of_citation_ids_referenced)
        """
        system_prompt = """You are a conversational AI assistant.

CORE BEHAVIOR:
- Always understand the user's intent before formatting.
- Use your own knowledge as the primary source.
- Use document context only as optional hints.
- Never blindly reformat text without understanding meaning.

FORMATTING RULES:
- Use paragraphs for explanations and descriptions.
- Use bullet points ONLY for naturally enumerable items.
- Never convert descriptive paragraphs into bullets.

DOCUMENT RULES:
- Use document context silently.
- Never mention documents unless explicitly asked.
- If documents do not contain the answer, use general knowledge confidently.

STYLE:
- Friendly, clean, human-like responses
- Clear spacing, readable formatting"""

        # Build user prompt based on context
        if has_context and context:
            user_prompt = f"""CONTEXT (optional hints, do not mention in answer):
{context}

USER QUESTION:
{question}

Answer the question naturally.
Use paragraphs for explanations and bullets for lists as appropriate."""
        else:
            user_prompt = f"""USER QUESTION:
{question}

Answer the question naturally.
Use paragraphs for explanations and bullets for lists as appropriate."""

        from shared.llm.factory import get_llm_provider
        llm = get_llm_provider()
        answer = await llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=1000,
        )
        answer = self._sanitize_output(answer)
        
        # Extract citation IDs from answer (supports multiple formats)
        import re
        # Try standard format first: [1], [2], etc. (most common)
        citation_ids = [int(match) for match in re.findall(r'\[(\d+)\]', answer)]
        # Fallback to emoji format: 📄[1], 📄[2], etc.
        if not citation_ids:
            citation_ids = [int(match) for match in re.findall(r'📄\[(\d+)\]', answer)]
        # Fallback to old format for backward compatibility
        if not citation_ids:
            citation_ids = [int(match) for match in re.findall(r'\[CITATION (\d+)\]', answer)]
        
        return answer, citation_ids
    
    def _renumber_and_map_citations(
        self,
        answer: str,
        chunks: List[Dict],
        document_names: Dict[str, str]
    ) -> tuple[str, List[Dict]]:
        """
        Renumber citations in the answer to be sequential (1, 2, 3...) based on appearance,
        and generate the corresponding citation metadata.
        
        Example: 
        Input text: "Fact A [3]. Fact B [5]. Fact C [3]."
        Output text: "Fact A [1]. Fact B [2]. Fact C [1]."
        Citations: [Metadata for chunk 3 (as id=1), Metadata for chunk 5 (as id=2)]
        """
        import re
        
        # 1. extract all citation IDs in order of appearance
        # Matches [123] and [CITATION 123] and 📄[123]
        pattern = r'(?:📄)?\[(?:CITATION )?(\d+)\]'
        matches = list(re.finditer(pattern, answer))
        
        if not matches:
            return answer, []
            
        # 2. Build mapping from Old ID -> New ID (preserving first appearance order)
        old_id_to_new_id = {}
        new_id_counter = 1
        
        for match in matches:
            old_id = int(match.group(1))
            if old_id not in old_id_to_new_id:
                old_id_to_new_id[old_id] = new_id_counter
                new_id_counter += 1
                
        # 3. Replace citations in text
        # We use a callback to ensure we replace exact matches correctly
        def replace_callback(match):
            old_id = int(match.group(1))
            if old_id in old_id_to_new_id:
                return f"[{old_id_to_new_id[old_id]}]"
            return match.group(0)
            
        new_answer = re.sub(pattern, replace_callback, answer)
        
        # 4. Generate citation metadata using the mapping
        citations = []
        
        # Iterate 1..N to maintain list order
        # Invert map to find which Old ID corresponds to New ID 1, 2, 3...
        new_id_to_old_id = {v: k for k, v in old_id_to_new_id.items()}
        
        for i in range(1, new_id_counter):
            old_id = new_id_to_old_id[i]
            
            # Verify old_id is valid for chunks list (1-based index)
            if 1 <= old_id <= len(chunks):
                chunk = chunks[old_id - 1] # Convert to 0-based
                
                citation = {
                    "id": i, # NEW sequential ID
                    "document_id": chunk["document_id"],
                    "document_name": document_names.get(chunk["document_id"], "Unknown Document"),
                    "file_name": document_names.get(chunk["document_id"], "Unknown Document"),
                    "page": chunk["page"],
                    "page_number": chunk["page"],
                    "start_char": chunk["start_char"],
                    "end_char": chunk["end_char"],
                    "quote": chunk["text"][:5000],
                    "text_snippet": chunk["text"][:1000],
                    "chunk_id": chunk.get("chunk_id", "")
                }
                citations.append(citation)
        
        return new_answer, citations

    def _map_citations(
        self,
        citation_ids: List[int],
        chunks: List[Dict],
        document_names: Dict[str, str]
    ) -> List[Dict]:
        """
        Map citation IDs to actual citation metadata.
        DEPRECATED: Use _renumber_and_map_citations instead for sequential ordering. 
        Kept for backward compatibility or internal use.
        """
        citations = []
        
        for citation_id in citation_ids:
            if 1 <= citation_id <= len(chunks):
                chunk = chunks[citation_id - 1]  # Convert to 0-based index
                
                citation = {
                    "id": citation_id,
                    "document_id": chunk["document_id"],
                    "document_name": document_names.get(chunk["document_id"], "Unknown Document"),
                    "file_name": document_names.get(chunk["document_id"], "Unknown Document"),  # Alias for frontend
                    "page": chunk["page"],
                    "page_number": chunk["page"],  # Alias for frontend
                    "start_char": chunk["start_char"],
                    "end_char": chunk["end_char"],
                    "quote": chunk["text"][:5000],  # Quote text for highlighting
                    "text_snippet": chunk["text"][:1000],  # First 1000 chars
                    "chunk_id": chunk.get("chunk_id", ""),  # For reference
                    "bbox": None  # Optional: bounding boxes for precise highlighting
                }
                citations.append(citation)
        
        # Remove duplicates based on (document_id, page, start_char)
        seen = set()
        unique_citations = []
        for citation in citations:
            key = (citation["document_id"], citation["page"], citation["start_char"])
            if key not in seen:
                seen.add(key)
                unique_citations.append(citation)
        
        return unique_citations
    
    async def _get_document_names(self, document_ids: List[str]) -> Dict[str, str]:
        """Get document names for citation display."""
        if not document_ids:
            return {}
        
        supabase = await get_supabase_client()
        
        # Get unique document IDs
        unique_ids = list(set(document_ids))
        
        # Query database
        result = supabase.table("documents").select("document_id, name").in_("document_id", unique_ids).execute()
        
        return {doc["document_id"]: doc["name"] for doc in result.data}
    
    async def _classify_intent(self, question: str) -> str:
        """
        Classify user intent using lightweight classification.
        
        Returns: "document_vault" | "content_query" | "general_knowledge"
        """
        # Quick keyword-based classification (fast and cheap)
        question_lower = question.lower()
        
        # Document vault keywords (require both domain + possession)
        document_keywords = ["document", "file", "pdf", "docx", "vault", "uploaded", "upload"]
        possession_keywords = ["my", "i have", "mine", "what i", "which i"]
        
        has_document_keyword = any(keyword in question_lower for keyword in document_keywords)
        has_possession_keyword = any(keyword in question_lower for keyword in possession_keywords)
        is_explicit_vault = any(query in question_lower for query in ["what documents", "what files", "document vault", "all documents", "all files"])
        
        if (has_document_keyword and has_possession_keyword) or is_explicit_vault:
            return "document_vault"
        
        # Default to content_query (will use RAG)
        return "content_query"
    
    def _is_meta_query(self, question: str) -> bool:
        """
        Check if question is about the document vault (meta-query).
        
        DEPRECATED: Use _classify_intent() instead.
        Kept for backward compatibility.
        """
        question_lower = question.lower()
        
        # Document-related keywords (domain check)
        document_keywords = [
            "document", "file", "pdf", "docx", "vault",
            "uploaded", "upload"
        ]
        
        # Possession keywords (ownership check)
        possession_keywords = [
            "my", "i have", "mine", "what i", "which i",
            "my documents", "my files", "documents i", "files i"
        ]
        
        # Check for document-related keywords
        has_document_keyword = any(keyword in question_lower for keyword in document_keywords)
        
        # Check for possession keywords (implies user asking about their own documents)
        has_possession_keyword = any(keyword in question_lower for keyword in possession_keywords)
        
        # Also check for explicit vault queries
        explicit_vault_queries = [
            "what documents", "what files", "document vault",
            "all documents", "all files"
        ]
        is_explicit_vault_query = any(query in question_lower for query in explicit_vault_queries)
        
        # Meta-query ONLY if:
        # 1. Has document keyword AND possession keyword, OR
        # 2. Is explicit vault query
        return (has_document_keyword and has_possession_keyword) or is_explicit_vault_query
    
    async def _get_user_documents(self, user_id: str) -> List[Dict]:
        """Get user's document list from database."""
        from app.database.supabase_client import is_local_mode

        if is_local_mode():
            from app.database.supabase_client import get_local_db
            docs, _ = get_local_db().list_documents(user_id, 0, 9999)
            return docs
        else:
            supabase = await get_supabase_client()
            result = supabase.table("documents").select(
                "document_id, name, file_size, status, uploaded_at"
            ).eq("user_id", user_id).order("uploaded_at", desc=True).execute()
            return result.data if result.data else []
    
    async def _answer_about_document_vault(
        self,
        question: str,
        documents: List[Dict]
    ) -> str:
        """Answer questions about the document vault using document list."""
        if not documents:
            return "You don't have any documents uploaded yet. Upload PDF documents to get started!"
        
        question_lower = question.lower()
        
        # For simple list requests, return clean list of file names only
        if any(keyword in question_lower for keyword in ["list", "what files", "show files", "what documents", "show documents", "files you have", "documents you have"]):
            document_names = [doc.get("name", "Unknown") for doc in documents]
            # Return simple clean list
            if len(document_names) == 1:
                return f"- {document_names[0]}"
            else:
                return "\n".join([f"- {name}" for name in document_names])
        
        # Format document list for context (for other queries)
        document_list = []
        for doc in documents:
            doc_name = doc.get("name", "Unknown")
            status = doc.get("status", "unknown")
            file_size = doc.get("file_size", 0)
            # Format file size
            if file_size > 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            elif file_size > 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size} bytes"
            
            document_list.append(f"- {doc_name} ({size_str}, Status: {status})")
        
        document_list_text = "\n".join(document_list)
        
        # Use LLM to answer naturally about the document list
        system_prompt = """You are a friendly AI assistant that helps users manage their document vault.

You have access to the user's document list. Answer questions about their documents naturally and helpfully, like ChatGPT.

Formatting & style rules:
- Use normal paragraphs for explanations.
- Use bullet points ONLY when listing multiple documents (e.g. "list all documents").
- Keep responses clean, readable, and conversational.
- Use light emojis when appropriate (1–2 per response) 📚📄

Rules:
1. If asked to list documents, provide a clear, natural list of document names (use bullets for lists).
2. If asked about document count, provide the number naturally in a paragraph.
3. If asked about specific documents, check if they exist in the list.
4. Be concise and helpful.
5. Don't make up documents that aren't in the list.
6. Default to paragraphs unless listing multiple items."""

        user_prompt = f"""USER'S DOCUMENT VAULT:
{document_list_text}

USER QUESTION:
{question}

Answer the question about the user's documents naturally and helpfully. Use paragraphs for explanations, and use bullets only when listing multiple documents."""

        from shared.llm.factory import get_llm_provider
        llm = get_llm_provider()
        return await llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=500,
        )


    async def _fetch_neighbor_chunks(self, retrieved_chunks: List[Dict]) -> List[Dict]:
        """
        Fetch neighbor chunks (previous and next) for retrieved chunks.
        
        This implements "Window Retrieval" to ensure we have context surrounding
        the specific keyword match, solving issues where lists or sentences are cut off.
        
        Since we don't have a chunk_index column, we use start_char ordering.
        """
        if not retrieved_chunks:
            return []

        from app.database.supabase_client import is_local_mode

        # In local mode, skip neighbor expansion (chunks stored in Qdrant only)
        if is_local_mode():
            return retrieved_chunks

        supabase = await get_supabase_client()
        expanded_chunks = []
        processed_ids = set()

        import logging
        logger = logging.getLogger(__name__)
        
        for chunk in retrieved_chunks:
            # 1. Add the original chunk
            if chunk["chunk_id"] not in processed_ids:
                expanded_chunks.append(chunk)
                processed_ids.add(chunk["chunk_id"])
            
            # Handle both flat structure (from vector_store.search) and nested payload structure
            document_id = chunk.get("document_id") or chunk.get("payload", {}).get("document_id")
            current_start = chunk.get("start_char") or chunk.get("payload", {}).get("start_char")
            
            # Skip neighbor fetching if missing critical metadata
            if not document_id or current_start is None:
                continue

            # 2. Fetch NEXT chunk
            try:
                # Query: next chunk in same document (start_char > current)
                response = supabase.table("document_chunks") \
                    .select("*") \
                    .eq("document_id", document_id) \
                    .gt("start_char", current_start) \
                    .order("start_char", desc=False) \
                    .limit(1) \
                    .execute()
                
                if response.data:
                    next_chunk = response.data[0]
                    next_id = next_chunk["chunk_id"]
                    
                    if next_id not in processed_ids:
                        # Flatten structure to match retrieved chunks
                        formatted_next = {
                            "chunk_id": next_id,
                            "document_id": next_chunk["document_id"],
                            "user_id": next_chunk["user_id"],
                            "page": next_chunk["page"],
                            "start_char": next_chunk["start_char"],
                            "end_char": next_chunk["end_char"],
                            "text": next_chunk["text"],
                            "score": chunk.get("score", 0) * 0.95  # Slightly lower score for neighbors
                        }
                        expanded_chunks.append(formatted_next)
                        processed_ids.add(next_id)
                        
            except Exception as e:
                logger.warning(f"Error fetching next chunk for {chunk['chunk_id']}: {e}")
            
            # 3. Fetch PREVIOUS chunk
            try:
                # Query: prev chunk in same document (start_char < current)
                response = supabase.table("document_chunks") \
                    .select("*") \
                    .eq("document_id", document_id) \
                    .lt("start_char", current_start) \
                    .order("start_char", desc=True) \
                    .limit(1) \
                    .execute()
                
                if response.data:
                    prev_chunk = response.data[0]
                    prev_id = prev_chunk["chunk_id"]
                    
                    if prev_id not in processed_ids:
                        # Flatten structure to match retrieved chunks
                        formatted_prev = {
                            "chunk_id": prev_id,
                            "document_id": prev_chunk["document_id"],
                            "user_id": prev_chunk["user_id"],
                            "page": prev_chunk["page"],
                            "start_char": prev_chunk["start_char"],
                            "end_char": prev_chunk["end_char"],
                            "text": prev_chunk["text"],
                            "score": chunk.get("score", 0) * 0.95  # Slightly lower score for neighbors
                        }
                        # Insert previous chunk BEFORE the current chunk if possible, but appending is fine
                        # due to re-sorting later if needed. For now, just append.
                        expanded_chunks.append(formatted_prev)
                        processed_ids.add(prev_id)

            except Exception as e:
                logger.warning(f"Error fetching prev chunk for {chunk['chunk_id']}: {e}")
        
        # Sort expanded chunks by document and starting character to maintain reading order
        # This ensures the LLM reads text in the correct flow
        # Sort expanded chunks by document and starting character to maintain reading order
        # All chunks are now normalized to flat structure
        expanded_chunks.sort(key=lambda x: (
            x.get("document_id"),
            x.get("start_char")
        ))
        
        chunks_count = len(retrieved_chunks)
        expanded_count = len(expanded_chunks)
        if expanded_count > chunks_count:
            logger.info(f"Context expansion: {chunks_count} -> {expanded_count} chunks")
            
        return expanded_chunks

