"""
Regression tests for RAG system routing and formatting.

These tests ensure critical user queries are routed correctly
and formatted properly.
"""
import pytest
from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_list_top_movies_routing():
    """Test that 'list top movies' goes to content_query (not document_vault)."""
    service = RAGService()
    intent = await service._classify_intent("list top movies")
    assert intent == "content_query", "Should route to content_query, not document_vault"


@pytest.mark.asyncio
async def test_top_10_films_routing():
    """Test that 'top 10 films' goes to content_query."""
    service = RAGService()
    intent = await service._classify_intent("top 10 films")
    assert intent == "content_query", "Should route to content_query"


@pytest.mark.asyncio
async def test_what_movies_acted_routing():
    """Test that 'what movies he acted' goes to content_query."""
    service = RAGService()
    intent = await service._classify_intent("what movies he acted")
    assert intent == "content_query", "Should route to content_query"


@pytest.mark.asyncio
async def test_list_my_documents_routing():
    """Test that 'list my documents' goes to document_vault."""
    service = RAGService()
    intent = await service._classify_intent("list my documents")
    assert intent == "document_vault", "Should route to document_vault"


@pytest.mark.asyncio
async def test_what_files_i_have_routing():
    """Test that 'what files do I have' goes to document_vault."""
    service = RAGService()
    intent = await service._classify_intent("what files do I have")
    assert intent == "document_vault", "Should route to document_vault"


@pytest.mark.asyncio
async def test_highest_collected_film_routing():
    """Test that 'highest collected film' goes to content_query."""
    service = RAGService()
    intent = await service._classify_intent("highest collected film")
    assert intent == "content_query", "Should route to content_query"


def test_determine_format_style_list():
    """Test format style detection for list queries."""
    service = RAGService()
    
    # List indicators
    assert service._determine_format_style("list top movies") == "list"
    assert service._determine_format_style("top 10 films") == "list"
    assert service._determine_format_style("best films") == "list"
    assert service._determine_format_style("highest collected") == "list"
    assert service._determine_format_style("show me his movies") == "list"
    assert service._determine_format_style("top 5 films") == "list"
    assert service._determine_format_style("top 20 films") == "list"


def test_determine_format_style_paragraph():
    """Test format style detection for paragraph queries."""
    service = RAGService()
    
    # Paragraph indicators
    assert service._determine_format_style("who is simbu") == "paragraph"
    assert service._determine_format_style("what movies he acted") == "paragraph"
    assert service._determine_format_style("tell me about him") == "paragraph"
    assert service._determine_format_style("explain this") == "paragraph"


# Golden test prompts - expected behavior
GOLDEN_TESTS = [
    {
        "query": "list top movies",
        "expected_intent": "content_query",
        "expected_format": "list",
        "should_not_mention": ["document", "file", "pdf", "source"]
    },
    {
        "query": "top 10 films",
        "expected_intent": "content_query",
        "expected_format": "list",
        "should_not_mention": ["document", "file", "pdf", "source"]
    },
    {
        "query": "what movies he acted",
        "expected_intent": "content_query",
        "expected_format": "paragraph",
        "should_not_mention": ["document", "file", "pdf", "source"]
    },
    {
        "query": "list my documents",
        "expected_intent": "document_vault",
        "expected_format": "list",
        "should_not_mention": []
    },
    {
        "query": "what files do I have",
        "expected_intent": "document_vault",
        "expected_format": "list",
        "should_not_mention": []
    },
    {
        "query": "highest collected film",
        "expected_intent": "content_query",
        "expected_format": "list",
        "should_not_mention": ["document", "file", "pdf", "source"]
    },
]


@pytest.mark.asyncio
async def test_golden_prompts():
    """Test all golden prompts for correct routing and format detection."""
    service = RAGService()
    
    for test_case in GOLDEN_TESTS:
        query = test_case["query"]
        expected_intent = test_case["expected_intent"]
        expected_format = test_case["expected_format"]
        
        # Test intent classification
        intent = await service._classify_intent(query)
        assert intent == expected_intent, f"Query '{query}' should route to '{expected_intent}', got '{intent}'"
        
        # Test format detection
        format_style = service._determine_format_style(query)
        assert format_style == expected_format, f"Query '{query}' should use '{expected_format}' format, got '{format_style}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


