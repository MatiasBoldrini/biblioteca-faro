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
        self.chunk_size = 1000  # characters per chunk
        self.chunk_overlap = 200  # overlap between chunks
        
        # Create books directory if it doesn't exist
        os.makedirs(self.books_dir, exist_ok=True)
    
    def process_file(self, file_path):
        """Process uploaded file and store in books directory"""
        filename = os.path.basename(file_path)
        # Add UUID to avoid filename conflicts
        base_name = Path(filename).stem
        extension = Path(filename).suffix
        unique_filename = f"{base_name}_{uuid.uuid4().hex[:8]}{extension}"
        
        destination = os.path.join(self.books_dir, unique_filename)
        shutil.copy2(file_path, destination)
        
        print(f"Processed file: {filename} -> {destination}")
        return destination
    
    def get_all_books(self):
        """Return list of all book files in the books directory"""
        if not os.path.exists(self.books_dir):
            return []
        
        all_files = []
        for file in os.listdir(self.books_dir):
            file_path = os.path.join(self.books_dir, file)
            if os.path.isfile(file_path) and file.lower().endswith(('.pdf', '.txt', '.doc', '.docx')):
                all_files.append(file_path)
        
        return all_files
    
    def extract_text_with_metadata(self, file_path):
        """Extract text from file with metadata (page numbers, etc.)"""
        file_extension = os.path.splitext(file_path)[1].lower()
        book_name = os.path.basename(file_path)
        
        if file_extension == '.pdf':
            return self._process_pdf(file_path, book_name)
        elif file_extension == '.txt':
            return self._process_txt(file_path, book_name)
        elif file_extension in ['.doc', '.docx']:
            return self._process_docx(file_path, book_name)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    def _process_pdf(self, file_path, book_name):
        """Extract text from PDF file with page numbers"""
        chunks = []
        try:
            doc = fitz.open(file_path)
            full_text = ""
            
            for page_num, page in enumerate(doc):
                # Try to get text directly
                page_text = page.get_text()
                
                # If the page has very little text, it might be a scanned image
                # Try OCR if the page text is too short
                if len(page_text.strip()) < 100:
                    try:
                        # Convert page to image
                        pix = page.get_pixmap()
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        # Use pytesseract for OCR
                        page_text = pytesseract.image_to_string(img)
                    except Exception as e:
                        print(f"OCR failed for page {page_num+1}: {e}")
                
                # Clean text (remove excessive whitespace)
                page_text = re.sub(r'\s+', ' ', page_text).strip()
                
                if page_text:
                    # Add page metadata
                    full_text += f"\n\n[PAGE {page_num+1}]\n{page_text}"
            
            # Create chunks with page information
            chunks = self._create_chunks_with_metadata(full_text, book_name)
            
        except Exception as e:
            print(f"Error processing PDF {file_path}: {e}")
        
        return chunks
    
    def _process_txt(self, file_path, book_name):
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            return self._create_chunks_with_metadata(text, book_name)
        except Exception as e:
            print(f"Error processing TXT {file_path}: {e}")
            return []
    
    def _process_docx(self, file_path, book_name):
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            full_text = "\n\n".join([para.text for para in doc.paragraphs])
            return self._create_chunks_with_metadata(full_text, book_name)
        except Exception as e:
            print(f"Error processing DOCX {file_path}: {e}")
            return []
    
    def _create_chunks_with_metadata(self, text, book_name):
        """Split text into chunks with overlapping and track page numbers"""
        chunks = []
        
        # Patrón para detectar marcadores de página:
        # - [PAGE número]
        # - página número (aceptando acento)
        # - un número en línea sola
        # - dos números separados por guión en línea sola (se toma el primero)
        page_pattern = (
            r"(?:\[PAGE (\d+)\])|"
            r"(?:p[aá]gina\s+(\d+))|"
            r"(?:\n\s*(\d+)\s*\n)|"
            r"(?:\n\s*(\d+)-\d+\s*\n)"
        )
        
        page_positions = {}
        for match in re.finditer(page_pattern, text, flags=re.IGNORECASE):
            page_num = None
            if match.group(1):
                page_num = match.group(1)
            elif match.group(2):
                page_num = match.group(2)
            elif match.group(3):
                page_num = match.group(3)
            elif match.group(4):
                page_num = match.group(4)
            
            # Guarda la posición del marcador para asignarlo luego al chunk
            position = match.start()
            page_positions[position] = page_num
        
        # Elimina los marcadores de página del texto
        clean_text = re.sub(page_pattern, "", text, flags=re.IGNORECASE)
        
        # Creación de chunks
        start = 0
        while start < len(clean_text):
            # Determina la página actual para esta posición
            current_page = "N/A"
            for pos, page in sorted(page_positions.items()):
                if pos <= start:
                    current_page = page
                else:
                    break
            
            end = start + self.chunk_size
            chunk_text = clean_text[start:end]
            
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text.strip(),
                    "page": current_page,
                    "book": book_name
                })
            
            start = end - self.chunk_overlap
        
        return chunks
