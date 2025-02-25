import io
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

import docx
import fitz  # PyMuPDF
import pytesseract
from PIL import Image


class DocumentService:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.books_dir = os.path.join(self.base_dir, 'books')
        os.makedirs(self.books_dir, exist_ok=True)
    
    def process_file(self, file_path):
        """Process an uploaded file and save as text in books folder"""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Generate a unique filename for the processed text
        original_filename = os.path.basename(file_path)
        safe_name = re.sub(r'[^\w\-.]', '_', original_filename)
        base_name = os.path.splitext(safe_name)[0]
        book_id = str(uuid.uuid4())[:8]
        output_filename = f"{base_name}_{book_id}.txt"
        output_path = os.path.join(self.books_dir, output_filename)
        
        # Extract text based on file type
        if file_extension == '.pdf':
            text = self._extract_text_from_pdf(file_path)
        elif file_extension == '.txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        elif file_extension in ['.doc', '.docx']:
            text = self._extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        # Save processed text to books directory
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"Processed {original_filename} and saved as {output_filename}")
        return output_path
    
    def _extract_text_from_pdf(self, file_path):
        """Extract text from PDF with page numbers"""
        doc = fitz.open(file_path)
        text = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            
            # Add page marker at the beginning of each page
            page_marker = f"\n\n[PAGE:{page_num+1}]\n\n"
            
            # If page has very little text, it might be scanned - try OCR
            if len(page_text.strip()) < 50:
                print(f"Using OCR for page {page_num+1} of {file_path}")
                # Get page as image
                pix = page.get_pixmap(alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Use OCR to extract text
                ocr_text = pytesseract.image_to_string(img, lang='eng+spa')
                text += page_marker + ocr_text
            else:
                text += page_marker + page_text
        
        return text
    
    def _extract_text_from_docx(self, file_path):
        """Extract text from DOCX file with approximate page tracking"""
        try:
            doc = docx.Document(file_path)
            full_text = ""
            
            # Approximate page breaks (rough estimate)
            chars_per_page = 3000
            char_count = 0
            page_num = 1
            
            for paragraph in doc.paragraphs:
                if char_count > chars_per_page:
                    full_text += f"\n\n[PAGE:{page_num}]\n\n"
                    page_num += 1
                    char_count = 0
                
                full_text += paragraph.text + "\n"
                char_count += len(paragraph.text)
            
            return full_text
        except Exception as e:
            # For older .doc files or issues with docx
            print(f"Error processing docx: {e}, trying OCR")
            # Convert to PDF and then use PDF extraction
            return self._convert_and_extract(file_path)
    
    def _convert_and_extract(self, file_path):
        """Fallback method for difficult document formats"""
        # This would ideally use a library like LibreOffice via subprocess
        # For now, we'll return a placeholder message
        return f"Error: Could not extract text from {os.path.basename(file_path)}"
    
    def get_all_books(self):
        """Get paths to all books in the books directory"""
        return [os.path.join(self.books_dir, f) for f in os.listdir(self.books_dir) 
                if os.path.isfile(os.path.join(self.books_dir, f)) and f.endswith('.txt')]
    
    def extract_text_with_metadata(self, file_path):
        """Extract text from a file and break into chunks with metadata"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return []
        
        # Get basic metadata
        filename = os.path.basename(file_path)
        book_name = os.path.splitext(filename)[0]
        
        # Extract pages
        chunks = []
        page_pattern = r'\[PAGE:(\d+)\]\s*\n*\s*(.*?)(?=\[PAGE:|\Z)'
        page_matches = re.finditer(page_pattern, text, re.DOTALL)
        
        pages_data = []
        for match in page_matches:
            page_num = int(match.group(1))
            page_text = match.group(2).strip()
            if page_text:  # Skip empty pages
                pages_data.append((page_num, page_text))
        
        # If no page markers found (e.g., for txt files), process as a single chunk
        if not pages_data:
            paragraph_chunks = self._split_into_chunks(text, chunk_size=1000, overlap=150)
            for i, chunk_text in enumerate(paragraph_chunks):
                chunks.append({
                    'text': chunk_text,
                    'source': filename,
                    'book': book_name,
                    'page': 'N/A',
                    'chunk': i,
                    'total_chunks': len(paragraph_chunks)
                })
        else:
            # Process each page
            for page_num, page_text in pages_data:
                # Split long pages into chunks
                if len(page_text) > 1500:
                    page_chunks = self._split_into_chunks(page_text, chunk_size=1000, overlap=150)
                    for i, chunk_text in enumerate(page_chunks):
                        chunks.append({
                            'text': chunk_text,
                            'source': filename,
                            'book': book_name,
                            'page': page_num,
                            'chunk': i,
                            'total_page_chunks': len(page_chunks)
                        })
                else:
                    # Short page - use as a single chunk
                    chunks.append({
                        'text': page_text,
                        'source': filename,
                        'book': book_name,
                        'page': page_num,
                        'chunk': 0,
                        'total_page_chunks': 1
                    })
        
        return chunks
    
    def _split_into_chunks(self, text, chunk_size=1000, overlap=150):
        """Split text into overlapping chunks of approximately chunk_size characters"""
        # Clean and normalize text
        text = re.sub(r'\s+', ' ', text).strip()
        
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Find a good breaking point near chunk_size
            end = min(start + chunk_size, len(text))
            
            # Try to break at paragraph or sentence
            if end < len(text):
                # Look for paragraph break
                paragraph_break = text.rfind('\n\n', start, end)
                if paragraph_break != -1 and paragraph_break > start + 0.5 * chunk_size:
                    end = paragraph_break
                else:
                    # Look for sentence break (period followed by space)
                    sentence_break = text.rfind('. ', start, end)
                    if sentence_break != -1 and sentence_break > start + 0.5 * chunk_size:
                        end = sentence_break + 1  # Include the period
            
            chunks.append(text[start:end].strip())
            start = max(start + chunk_size - overlap, end - overlap)
        
        return chunks
