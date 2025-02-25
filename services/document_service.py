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
        self.max_chunk_size = 1500  # absolute maximum size for any chunk
        
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
        """Split text into chunks respecting paragraph boundaries when possible"""
        chunks = []
        
        # Patrón para detectar marcadores de página
        page_pattern = (
            r"(?:\[PAGE (\d+)\])|"            # [PAGE número]
            r"(?:p[aá]gina\s+(\d+))|"         # página número
            r"(?:\n\s*(\d+)\s*\n)|"           # \n número \n
            r"(?:\n\s*(\d+)-\d+\s*\n)|"       # \n número-numero \n
            r"(?:^(\d+)-\d+\n)|"              # número-numero\n (sin espacio a la izquierda)
            r"(?:^(\d+)-\d+\s*\n)"            # número-numero\n (con o sin espacio a la izquierda)
        )
        
        # Potenciales marcadores de sección (encabezados)
        section_pattern = r"\n\s*(?:[A-Z0-9\s]{2,}:?|[IVX]+\.|\d+\.\d+\.|\d+\.)\s*\n"
        
        # Track page numbers and their positions
        page_positions = {}
        for match in re.finditer(page_pattern, text, flags=re.IGNORECASE):
            page_num = None
            for g in match.groups():
                if g:
                    page_num = g
                    break
                
            
            if page_num:
                position = match.start()
                page_positions[position] = page_num
        
        # Remove page markers from text
        clean_text = re.sub(page_pattern, "", text, flags=re.IGNORECASE)
        
        # Split text into paragraphs
        paragraphs = re.split(r'\n\s*\n', clean_text)
        
        current_chunk = ""
        current_position = 0
        processed_length = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                processed_length += 2  # Account for paragraph separators
                continue
                
            # Check if paragraph is a section heading
            is_section_heading = bool(re.match(section_pattern, "\n" + paragraph + "\n"))
            
            # If adding this paragraph would exceed chunk size or if it's a new section
            if len(current_chunk) + len(paragraph) > self.chunk_size or is_section_heading:
                # Save current chunk if not empty
                if current_chunk.strip():
                    # Determine the page for this chunk
                    current_page = self._get_page_for_position(current_position, page_positions)
                    chunks.append({
                        "text": current_chunk.strip(),
                        "page": current_page,
                        "book": book_name
                    })
                
                # Start a new chunk
                current_chunk = paragraph
                current_position = processed_length
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
                    current_position = processed_length
            
            processed_length += len(paragraph) + 2  # +2 for paragraph separators
            
            # Handle paragraphs that are longer than chunk_size
            if len(paragraph) > self.max_chunk_size:
                # Try to split by sentences
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                temp_chunk = ""
                sentence_position = current_position
                
                for sentence in sentences:
                    if len(temp_chunk) + len(sentence) > self.max_chunk_size:
                        if temp_chunk:
                            # Save the accumulated sentences
                            current_page = self._get_page_for_position(sentence_position, page_positions)
                            chunks.append({
                                "text": temp_chunk.strip(),
                                "page": current_page,
                                "book": book_name
                            })
                            
                            # Reset for new chunk
                            sentence_position += len(temp_chunk)
                            temp_chunk = sentence
                        else:
                            # Handle extremely long sentences by character splitting
                            for i in range(0, len(sentence), self.max_chunk_size):
                                sub_sentence = sentence[i:i + self.max_chunk_size]
                                if sub_sentence.strip():
                                    sub_position = sentence_position + i
                                    current_page = self._get_page_for_position(sub_position, page_positions)
                                    chunks.append({
                                        "text": sub_sentence.strip(),
                                        "page": current_page,
                                        "book": book_name
                                    })
                    else:
                        if temp_chunk:
                            temp_chunk += " " + sentence
                        else:
                            temp_chunk = sentence
                
                # Add the last chunk if not empty
                if temp_chunk.strip():
                    current_page = self._get_page_for_position(sentence_position, page_positions)
                    chunks.append({
                        "text": temp_chunk.strip(),
                        "page": current_page,
                        "book": book_name
                    })
                
                # Reset current chunk since we've handled this long paragraph
                current_chunk = ""
        
        # Don't forget the last chunk
        if current_chunk.strip():
            current_page = self._get_page_for_position(current_position, page_positions)
            chunks.append({
                "text": current_chunk.strip(),
                "page": current_page,
                "book": book_name
            })
        
        return chunks
    
    def _get_page_for_position(self, position, page_positions):
        """Determine the page number for a given position in the text"""
        current_page = "N/A"
        for pos, page in sorted(page_positions.items()):
            if pos <= position:
                current_page = page
            else:
                break
        return current_page
