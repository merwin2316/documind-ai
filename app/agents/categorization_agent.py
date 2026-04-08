"""
AI agent for automatic document categorization.
Analyzes document content and generates metadata.
"""
from openai import AsyncOpenAI
from typing import Dict, List, Optional
import json
from config import settings


class CategorizationAgent:
    """AI agent for document categorization and metadata extraction."""
    
    CATEGORIES = [
        "Legal",
        "Financial", 
        "Product",
        "Marketing",
        "HR",
        "Operations",
        "Research",
        "Other"
    ]
    
    SYSTEM_PROMPT = """You are a document categorization expert. Analyze the document content and provide:

1. **Category**: Choose ONE from: Legal, Financial, Product, Marketing, HR, Operations, Research, Other
2. **Tags**: 3-5 relevant, specific tags (e.g., "contract", "Q4-2024", "confidential", "series-a")
3. **Summary**: 2-3 sentences describing what this document is about
4. **Key Entities**: Important people, companies, and products mentioned

Be specific and accurate. Tags should be lowercase and use hyphens for multi-word tags.

Return ONLY valid JSON in this exact format:
{
    "category": "Legal",
    "tags": ["contract", "series-a", "investment", "2024"],
    "summary": "Investment agreement for Series A funding round with Acme Ventures. Outlines terms, conditions, and equity distribution.",
    "key_entities": {
        "people": ["John Doe", "Jane Smith"],
        "companies": ["Acme Ventures", "TechCorp"],
        "products": ["ProductX"]
    }
}"""
    
    def __init__(self):
        """Initialize categorization agent with OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def categorize_document(
        self, 
        document_text: str, 
        filename: str
    ) -> Dict:
        """
        Analyze document and generate categorization metadata.
        
        Args:
            document_text: Sample text from document (first ~3000 chars)
            filename: Document filename (provides additional context)
        
        Returns:
            Dict with category, tags, summary, key_entities
        """
        # Truncate text to first 3000 characters for efficiency
        # This is usually enough to understand document type and content
        sample_text = document_text[:3000]
        
        user_prompt = f"""Document Filename: {filename}

Content Sample:
{sample_text}

Analyze this document and provide categorization metadata in JSON format."""
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Low temperature for consistent categorization
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate and normalize result
            return self._validate_result(result)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error categorizing document: {e}")
            
            # Return default categorization on error
            return {
                "category": "Other",
                "tags": ["uncategorized"],
                "summary": f"Document: {filename}",
                "key_entities": {"people": [], "companies": [], "products": []}
            }
    
    def _validate_result(self, result: Dict) -> Dict:
        """Validate and normalize categorization result."""
        # Ensure category is valid
        if result.get("category") not in self.CATEGORIES:
            result["category"] = "Other"
        
        # Ensure tags is a list
        if not isinstance(result.get("tags"), list):
            result["tags"] = []
        
        # Normalize tags (lowercase, limit to 5)
        result["tags"] = [tag.lower().strip() for tag in result["tags"][:5]]
        
        # Ensure summary exists
        if not result.get("summary"):
            result["summary"] = "No summary available"
        
        # Ensure key_entities structure
        if not isinstance(result.get("key_entities"), dict):
            result["key_entities"] = {"people": [], "companies": [], "products": []}
        
        return result
    
    async def find_related_documents(
        self,
        document_id: str,
        user_id: str,
        top_k: int = 5
    ) -> List[str]:
        """
        Find related documents using vector similarity.
        Uses existing Qdrant embeddings to find semantically similar documents.
        
        Args:
            document_id: ID of the document to find relations for
            user_id: User ID for filtering
            top_k: Number of related documents to return
        
        Returns:
            List of related document IDs
        """
        try:
            from app.services.vector_store import VectorStore
            from app.database.supabase_client import get_supabase_client
            
            # Get chunks for this document
            supabase = await get_supabase_client()
            chunks_result = supabase.table("document_chunks").select("chunk_id").eq(
                "document_id", document_id
            ).limit(3).execute()
            
            if not chunks_result.data:
                return []
            
            # Use first chunk to find similar documents
            first_chunk_id = chunks_result.data[0]["chunk_id"]
            
            vector_store = VectorStore()
            # Search for similar chunks
            similar_chunks = await vector_store.search(
                query="",  # Empty query since we use chunk_id
                user_id=user_id,
                limit=top_k * 3,  # Get more to filter by document
                chunk_id=first_chunk_id  # Search by chunk embedding
            )
            
            # Extract unique document IDs (excluding current document)
            related_doc_ids = []
            seen_docs = set()
            
            for chunk in similar_chunks:
                doc_id = chunk.get("document_id")
                if doc_id and doc_id != document_id and doc_id not in seen_docs:
                    related_doc_ids.append(doc_id)
                    seen_docs.add(doc_id)
                    
                    if len(related_doc_ids) >= top_k:
                        break
            
            return related_doc_ids
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error finding related documents: {e}")
            return []
