"""
Document processing service for PDF and DOCX files.
Handles text extraction, chunking, and metadata management.
"""
from io import BytesIO
from typing import List, Dict
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
import uuid
from config import settings
import tiktoken
import re


class DocumentProcessor:
    """
    Process documents (PDF, DOCX) for RAG system.
    Extracts text, creates chunks with metadata, and stores in database.
    """
    
    def __init__(self):
        """Initialize document processor with tokenizer for production-level chunking."""
        # Initialize tokenizer for GPT-4 (used for token counting)
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            # Fallback to cl100k_base encoding (used by gpt-4, gpt-3.5-turbo)
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    async def process_document(
        self, 
        file_content: bytes,
        filename: str,
        document_id: str,
        user_id: str
    ) -> List[Dict]:
        """
        Process document: extract text, chunk with metadata.
        Supports both PDF and DOCX files.
        
        Returns list of chunks with:
        - chunk_id
        - document_id
        - user_id
        - page number (or section number for DOCX)
        - start_char, end_char
        - text
        """
        # Determine file type
        if filename.lower().endswith('.pdf'):
            return await self.process_pdf(file_content, document_id, user_id)
        elif filename.lower().endswith('.docx'):
            return await self.process_docx(file_content, document_id, user_id)
        else:
            raise ValueError(f"Unsupported file type: {filename}")
    
    async def process_pdf(
        self, 
        file_content: bytes, 
        document_id: str,
        user_id: str
    ) -> List[Dict]:
        """
        Process PDF: extract text page by page, chunk with metadata.
        
        Returns list of chunks with:
        - chunk_id
        - document_id
        - user_id
        - page number
        - start_char, end_char
        - text
        """
        # Read PDF
        pdf_file = BytesIO(file_content)
        reader = PdfReader(pdf_file)
        
        chunks = []
        
        # Process each page
        for page_num, page in enumerate(reader.pages, start=1):
            # Extract text from page
            page_text = page.extract_text()
            
            if not page_text.strip():
                continue
            
            # Chunk the page text
            page_chunks = self._chunk_text(
                page_text,
                page_num,
                document_id,
                user_id
            )
            
            chunks.extend(page_chunks)
        
        # Store chunks in database
        await self._store_chunks_metadata(chunks)
        
        return chunks
    
    async def process_docx(
        self,
        file_content: bytes,
        document_id: str,
        user_id: str
    ) -> List[Dict]:
        """
        Process DOCX: extract text from paragraphs, tables, and preserve structure.
        
        For DOCX files, we treat each paragraph group (or logical section) as a "page"
        for consistency with the database schema.
        
        Returns list of chunks with:
        - chunk_id
        - document_id
        - user_id
        - page number (section number for DOCX)
        - start_char, end_char
        - text
        """
        # Read DOCX
        docx_file = BytesIO(file_content)
        doc = DocxDocument(docx_file)
        
        chunks = []
        text_parts = []
        
        # Extract text from paragraphs
        for para in doc.paragraphs:
            para_text = para.text.strip()
            if para_text:
                text_parts.append(para_text)
        
        # Extract text from tables (important for structured data)
        for table in doc.tables:
            table_text_parts = []
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if cell_text:
                        row_text.append(cell_text)
                if row_text:
                    # Join cells with tab separator to preserve table structure
                    table_text_parts.append(" | ".join(row_text))
            
            if table_text_parts:
                # Add table as a block with clear separator
                text_parts.append("\n[Table]\n" + "\n".join(table_text_parts) + "\n[/Table]")
        
        # Combine all text parts
        full_text = "\n\n".join(text_parts)
        
        if not full_text.strip():
            # If no text extracted, return empty chunks
            return []
        
        # Log extraction stats
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Extracted {len(full_text)} characters from DOCX file")
        
        # Split into sections (roughly by character count, preserving paragraph boundaries)
        # We'll treat sections similar to pages for consistency
        sections = self._split_into_sections(full_text)
        logger.info(f"Split DOCX into {len(sections)} sections (treated as pages)")
        
        # Process each section (treat as "page" for consistency)
        for section_num, section_text in enumerate(sections, start=1):
            if not section_text.strip():
                continue
            
            # Chunk the section text
            section_chunks = self._chunk_text(
                section_text,
                section_num,  # Use section number as "page" number
                document_id,
                user_id
            )
            
            chunks.extend(section_chunks)
        
        # Store chunks in database
        await self._store_chunks_metadata(chunks)
        
        logger.info(f"Created {len(chunks)} total chunks across {len(sections)} sections for DOCX")
        
        return chunks
    
    def _split_into_sections(self, text: str, section_size: int = 2000) -> List[str]:
        """
        Split text into sections for DOCX processing.
        Sections are roughly section_size characters (reduced from 5000 to 2000 for better granularity),
        split at paragraph boundaries.
        Each section is treated as a "page" for consistency with PDF processing.
        """
        if len(text) <= section_size:
            return [text]
        
        sections = []
        paragraphs = text.split("\n\n")
        current_section = ""
        
        for para in paragraphs:
            if len(current_section) + len(para) > section_size and current_section:
                sections.append(current_section.strip())
                current_section = para
            else:
                if current_section:
                    current_section += "\n\n" + para
                else:
                    current_section = para
        
        if current_section:
            sections.append(current_section.strip())
        
        return sections if sections else [text]
    
    def _chunk_text(
        self,
        text: str,
        page: int,
        document_id: str,
        user_id: str
    ) -> List[Dict]:
        """
        PRODUCTION-LEVEL: Token-based chunking with semantic sentence splitting.
        
        Uses tiktoken for accurate token counting and splits at sentence boundaries
        to preserve semantic meaning. This is the industry-standard approach for RAG systems.
        
        Each chunk includes:
        - chunk_id (unique UUID)
        - page number (or section number for DOCX)
        - start_char, end_char (character positions)
        - text (chunk content)
        - token_count (for monitoring)
        """
        chunks = []
        
        # Use token-based chunking if enabled (production setting)
        if settings.CHUNK_METHOD == "token" and settings.SEMANTIC_SPLITTING:
            return self._chunk_by_sentences(text, page, document_id, user_id)
        elif settings.CHUNK_METHOD == "token":
            return self._chunk_by_tokens(text, page, document_id, user_id)
        
        # Fallback to character-based chunking (legacy)
        return self._chunk_by_characters(text, page, document_id, user_id)
    
    def _chunk_by_sentences(
        self,
        text: str,
        page: int,
        document_id: str,
        user_id: str
    ) -> List[Dict]:
        """
        Token-based chunking with semantic sentence splitting.
        Preserves sentence boundaries for better context.
        """
        # Split text into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return []
        
        chunks = []
        current_sentences = []
        current_token_count = 0
        char_pos = 0
        
        chunk_size = settings.CHUNK_SIZE  # In tokens
        overlap = settings.CHUNK_OVERLAP  # In tokens
        
        for sentence in sentences:
            # Count tokens in this sentence
            sentence_tokens = len(self.tokenizer.encode(sentence))
            
            # If adding this sentence exceeds chunk size, create new chunk
            if current_token_count + sentence_tokens > chunk_size and current_sentences:
                # Create chunk from current sentences
                chunk_text = " ".join(current_sentences)
                
                chunk = {
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "user_id": user_id,
                    "page": page,
                    "start_char": char_pos,
                    "end_char": char_pos + len(chunk_text),
                    "text": chunk_text,
                    "token_count": current_token_count
                }
                chunks.append(chunk)
                
                # Calculate overlap: keep last few sentences for context
                overlap_sentences = []
                overlap_tokens = 0
                for sent in reversed(current_sentences):
                    sent_tokens = len(self.tokenizer.encode(sent))
                    if overlap_tokens + sent_tokens <= overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_tokens += sent_tokens
                    else:
                        break
                
                # Start new chunk with overlap + current sentence
                overlap_text = " ".join(overlap_sentences)
                char_pos += len(chunk_text) - len(overlap_text)
                current_sentences = overlap_sentences + [sentence]
                current_token_count = overlap_tokens + sentence_tokens
            else:
                # Add sentence to current chunk
                current_sentences.append(sentence)
                current_token_count += sentence_tokens
        
        # Add final chunk
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            chunk = {
                "chunk_id": str(uuid.uuid4()),
                "document_id": document_id,
                "user_id": user_id,
                "page": page,
                "start_char": char_pos,
                "end_char": char_pos + len(chunk_text),
                "text": chunk_text,
                "token_count": current_token_count
            }
            chunks.append(chunk)
        
        return chunks
    
    def _chunk_by_tokens(
        self,
        text: str,
        page: int,
        document_id: str,
        user_id: str
    ) -> List[Dict]:
        """
        Token-based chunking without sentence splitting.
        Faster but may split sentences.
        """
        chunks = []
        chunk_size = settings.CHUNK_SIZE
        overlap = settings.CHUNK_OVERLAP
        
        # Tokenize entire text
        tokens = self.tokenizer.encode(text)
        
        token_pos = 0
        char_pos = 0
        
        while token_pos < len(tokens):
            # Get chunk tokens
            end_token_pos = min(token_pos + chunk_size, len(tokens))
            chunk_tokens = tokens[token_pos:end_token_pos]
            
            # Decode back to text
            chunk_text = self.tokenizer.decode(chunk_tokens)
            
            # Create chunk
            chunk = {
                "chunk_id": str(uuid.uuid4()),
                "document_id": document_id,
                "user_id": user_id,
                "page": page,
                "start_char": char_pos,
                "end_char": char_pos + len(chunk_text),
                "text": chunk_text,
                "token_count": len(chunk_tokens)
            }
            chunks.append(chunk)
            
            # Move to next chunk with overlap
            token_pos = end_token_pos - overlap
            char_pos += len(chunk_text)
            
            # Prevent infinite loop
            if token_pos >= end_token_pos:
                break
        
        return chunks
    
    def _chunk_by_characters(
        self,
        text: str,
        page: int,
        document_id: str,
        user_id: str
    ) -> List[Dict]:
        """
        Legacy character-based chunking.
        Kept for backwards compatibility.
        """
        chunks = []
        chunk_size = settings.CHUNK_SIZE
        overlap = settings.CHUNK_OVERLAP
        
        # Track character positions
        char_pos = 0
        chunk_index = 0
        
        while char_pos < len(text):
            # Determine chunk boundaries
            end_pos = min(char_pos + chunk_size, len(text))
            
            # Extract chunk text
            chunk_text = text[char_pos:end_pos]
            
            # Create chunk ID (must be a valid UUID for Qdrant)
            # Qdrant requires point IDs to be either UUID or unsigned integer
            chunk_id = str(uuid.uuid4())
            
            # Create chunk metadata
            chunk = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "user_id": user_id,
                "page": page,
                "start_char": char_pos,
                "end_char": end_pos,
                "text": chunk_text
            }
            
            chunks.append(chunk)
            
            # Move to next chunk with overlap
            char_pos = end_pos - overlap
            chunk_index += 1
            
            # Prevent infinite loop
            if char_pos <= chunks[-1]["start_char"]:
                char_pos = end_pos
        
        return chunks
    
    async def _store_chunks_metadata(self, chunks: List[Dict]):
        """Store chunk metadata in local SQLite database."""
        if not chunks:
            return

        # Prepare chunks for insertion
        chunk_records = [
            {
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "user_id": chunk["user_id"],
                "page": chunk["page"],
                "start_char": chunk["start_char"],
                "end_char": chunk["end_char"],
                "text": chunk["text"]
            }
            for chunk in chunks
        ]

        from app.database.supabase_client import get_local_db
        get_local_db().insert_chunks(chunk_records)

