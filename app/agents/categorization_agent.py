"""
AI agent for automatic document categorization.
Analyzes document content and generates metadata.
"""
import json
import logging
from typing import Dict, List
from shared.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)


class CategorizationAgent:
    """AI agent for document categorization and metadata extraction."""

    CATEGORIES = [
        "Legal", "Financial", "Product", "Marketing",
        "HR", "Operations", "Research", "Other",
    ]

    SYSTEM_PROMPT = """You are a document categorization expert. Analyze the document content and provide:

1. **Category**: Choose ONE from: Legal, Financial, Product, Marketing, HR, Operations, Research, Other
2. **Tags**: 3-5 relevant, specific tags (lowercase, hyphens for multi-word)
3. **Summary**: 2-3 sentences describing what this document is about
4. **Key Entities**: Important people, companies, and products mentioned

Return ONLY valid JSON in this exact format:
{
    "category": "Legal",
    "tags": ["contract", "series-a", "investment"],
    "summary": "Investment agreement for Series A...",
    "key_entities": {
        "people": ["John Doe"],
        "companies": ["Acme Ventures"],
        "products": ["ProductX"]
    }
}"""

    def __init__(self):
        self.llm = get_llm_provider()

    async def categorize_document(self, document_text: str, filename: str) -> Dict:
        """Analyze document and generate categorization metadata."""
        sample_text = document_text[:3000]

        user_prompt = f"""Document Filename: {filename}

Content Sample:
{sample_text}

Analyze this document and provide categorization metadata in JSON format."""

        try:
            response = await self.llm.generate(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                json_mode=True,
            )
            result = json.loads(response)
            return self._validate_result(result)
        except Exception as e:
            logger.error(f"Error categorizing document: {e}")
            return {
                "category": "Other",
                "tags": ["uncategorized"],
                "summary": f"Document: {filename}",
                "key_entities": {"people": [], "companies": [], "products": []},
            }

    def _validate_result(self, result: Dict) -> Dict:
        if result.get("category") not in self.CATEGORIES:
            result["category"] = "Other"
        if not isinstance(result.get("tags"), list):
            result["tags"] = []
        result["tags"] = [t.lower().strip() for t in result["tags"][:5]]
        if not result.get("summary"):
            result["summary"] = "No summary available"
        if not isinstance(result.get("key_entities"), dict):
            result["key_entities"] = {"people": [], "companies": [], "products": []}
        return result

    async def find_related_documents(
        self, document_id: str, user_id: str, top_k: int = 5
    ) -> List[str]:
        """Find related documents using vector similarity."""
        try:
            from app.services.vector_store import VectorStore
            from app.database.supabase_client import get_supabase_client

            supabase = await get_supabase_client()
            chunks_result = (
                supabase.table("document_chunks")
                .select("chunk_id")
                .eq("document_id", document_id)
                .limit(3)
                .execute()
            )

            if not chunks_result.data:
                return []

            first_chunk_id = chunks_result.data[0]["chunk_id"]
            vector_store = VectorStore()
            similar_chunks = await vector_store.search(
                query="",
                user_id=user_id,
                top_k=top_k * 3,
                chunk_id=first_chunk_id,
            )

            related, seen = [], set()
            for chunk in similar_chunks:
                doc_id = chunk.get("document_id")
                if doc_id and doc_id != document_id and doc_id not in seen:
                    related.append(doc_id)
                    seen.add(doc_id)
                    if len(related) >= top_k:
                        break
            return related
        except Exception as e:
            logger.error(f"Error finding related documents: {e}")
            return []
