import os
import re
from pathlib import Path

import google.generativeai as genai
from dotenv import load_dotenv

from .document_service import DocumentService
from .vector_store_service import VectorStoreService
from .embedding_service import EmbeddingService

# Cargar variables de entorno
load_dotenv()

class ChapterService:
    def __init__(self, vector_store=None):
        """
        Servicio para gestionar operaciones relacionadas con capítulos de libros
        
        Args:
            vector_store: Instancia existente de VectorStoreService. Si es None, se crea una nueva.
        """
        self.document_service = DocumentService()
        # Usar vector_store existente o crear uno nuevo si no se proporciona
        self.vector_store = vector_store if vector_store is not None else VectorStoreService()
        
        # No necesitamos crear un embedding_service separado si usamos el de vector_store
        if vector_store is not None:
            self.embedding_service = vector_store.embedding_service
        else:
            self.embedding_service = EmbeddingService()
        
        # Configurar el modelo Gemini para resúmenes y comparaciones
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        self.model = genai.GenerativeModel(
            'models/gemini-1.5-pro',
            generation_config={'temperature': 0.3, 'top_p': 0.8}
        )
        
        # Patrones para identificar capítulos en el texto
        self.chapter_patterns = [
            r'(?i)capítulo\s+(\d+|[IVX]+)',
            r'(?i)capítulo\s+(\w+)',
            r'(?i)chapter\s+(\d+|[IVX]+)',
            r'^(\d+)\.\s+', # Formato: "1. Título del capítulo"
            r'\n(\d+)\.\s+', # Formato: después de salto de línea "1. Título"
            r'(?i)sección\s+(\d+|[IVX]+)',
            r'(?i)section\s+(\d+|[IVX]+)'
        ]
    
    def identify_chapters(self, book_name):
        """Identifica los capítulos disponibles en un libro específico"""
        try:
            # Obtener el path del libro
            book_path = None
            for file in self.document_service.get_all_books():
                if book_name in os.path.basename(file):
                    book_path = file
                    break
            
            if not book_path:
                return {"success": False, "message": f"Libro no encontrado: {book_name}"}
            
            # Obtener chunks del libro desde el vector store
            query = f"book:{os.path.basename(book_path)}"
            chunks = self._get_book_chunks(os.path.basename(book_path))
            
            if not chunks:
                return {"success": False, "message": f"No se encontraron chunks para el libro: {book_name}"}
            
            # Identificar patrones de capítulos en el texto
            chapters = {}
            for chunk in chunks:
                text = chunk['text']
                page = chunk['page']
                
                # Buscar patrones de capítulo
                for pattern in self.chapter_patterns:
                    matches = re.finditer(pattern, text)
                    for match in matches:
                        chapter_num = match.group(1)
                        start_pos = match.start()
                        
                        # Extraer título del capítulo (hasta 50 caracteres después del patrón)
                        title_end = min(start_pos + 100, len(text))
                        chapter_title = text[start_pos:title_end].strip()
                        
                        # Limpiar el título
                        chapter_title = re.sub(r'\n.*', '', chapter_title)
                        
                        if chapter_num not in chapters:
                            chapters[chapter_num] = {
                                "title": chapter_title,
                                "page": page,
                                "chunks": [chunk['index']]
                            }
                        else:
                            chapters[chapter_num]["chunks"].append(chunk['index'])
            
            # Ordenar capítulos
            sorted_chapters = []
            for chapter_num, data in chapters.items():
                sorted_chapters.append({
                    "chapter_number": chapter_num,
                    "title": data["title"],
                    "page": data["page"]
                })
            
            # Ordenar por número de capítulo (si es posible)
            try:
                sorted_chapters.sort(key=lambda x: int(x["chapter_number"]))
            except (ValueError, TypeError):
                # Si no se puede ordenar numéricamente, dejar como está
                pass
            
            return {"success": True, "book": book_name, "chapters": sorted_chapters}
        
        except Exception as e:
            return {"success": False, "message": f"Error al identificar capítulos: {str(e)}"}
    
    def summarize_chapter(self, book_name, chapter_identifier, summary_length="medium"):
        """Genera un resumen de un capítulo específico"""
        try:
            # Obtener los chunks del libro
            chunks = self._get_book_chunks(book_name)
            if not chunks:
                return {"success": False, "message": f"No se encontraron chunks para el libro: {book_name}"}
            
            # Buscar chunks relacionados con el capítulo
            chapter_chunks = []
            
            # Buscar por título o número de capítulo
            for chunk in chunks:
                text = chunk['text']
                for pattern in self.chapter_patterns:
                    matches = re.search(pattern, text)
                    if matches and matches.group(1) == str(chapter_identifier):
                        chapter_chunks.append(chunk)
                        break
            
            # Si no encontramos chunks por título, buscar usando vector search
            if not chapter_chunks:
                query = f"capítulo {chapter_identifier} {book_name}"
                search_results = self.vector_store.search(query, top_k=10)
                
                # Filtrar por libro y similaridad
                chapter_chunks = [r for r in search_results 
                                  if book_name in r['book'] and r['score'] > 0.4]
            
            if not chapter_chunks:
                return {"success": False, "message": f"No se encontró el capítulo {chapter_identifier} en el libro {book_name}"}
            
            # Ordenar chunks por página o índice
            chapter_chunks.sort(key=lambda x: int(x['page']) if x['page'].isdigit() else 0)
            
            # Construir contexto con el contenido del capítulo
            chapter_text = "\n\n".join([f"[Página {c['page']}] {c['text']}" for c in chapter_chunks])
            
            # Generar resumen
            summary_prompt = self._create_summary_prompt(chapter_text, summary_length)
            response = self.model.generate_content(summary_prompt)
            
            return {
                "success": True,
                "book": book_name,
                "chapter": chapter_identifier,
                "summary": response.text,
                "pages": [c['page'] for c in chapter_chunks]
            }
        
        except Exception as e:
            return {"success": False, "message": f"Error al resumir capítulo: {str(e)}"}
    
    def compare_chapters(self, sources):
        """
        Compara el contenido de múltiples capítulos
        sources = [{"book": "book1", "chapter": "1"}, {"book": "book2", "chapter": "2"}]
        """
        try:
            # Preparar información de cada fuente
            chapters_info = []
            
            for source in sources:
                book_name = source["book"]
                chapter = source["chapter"]
                
                # Buscar chunks de este capítulo
                chunks = self._get_book_chunks(book_name)
                chapter_chunks = []
                
                # Buscar por título o número de capítulo
                for chunk in chunks:
                    text = chunk['text']
                    for pattern in self.chapter_patterns:
                        matches = re.search(pattern, text)
                        if matches and matches.group(1) == str(chapter):
                            chapter_chunks.append(chunk)
                            break
                
                # Si no encontramos chunks por título, buscar usando vector search
                if not chapter_chunks:
                    query = f"capítulo {chapter} {book_name}"
                    search_results = self.vector_store.search(query, top_k=10)
                    
                    # Filtrar por libro y similaridad
                    chapter_chunks = [r for r in search_results 
                                      if book_name in r['book'] and r['score'] > 0.4]
                
                if chapter_chunks:
                    # Ordenar chunks y extraer texto
                    chapter_chunks.sort(key=lambda x: int(x['page']) if x['page'].isdigit() else 0)
                    chapter_text = "\n\n".join([f"{c['text']}" for c in chapter_chunks])
                    
                    chapters_info.append({
                        "book": book_name,
                        "chapter": chapter,
                        "text": chapter_text,
                        "pages": [c['page'] for c in chapter_chunks]
                    })
            
            if not chapters_info or len(chapters_info) < 2:
                return {"success": False, "message": "No se encontraron suficientes capítulos para comparar"}
            
            # Construir prompt para comparación
            comparison_prompt = self._create_comparison_prompt(chapters_info)
            response = self.model.generate_content(comparison_prompt)
            
            return {
                "success": True,
                "comparison": response.text,
                "sources": [{"book": info["book"], "chapter": info["chapter"]} for info in chapters_info]
            }
        
        except Exception as e:
            return {"success": False, "message": f"Error al comparar capítulos: {str(e)}"}
    
    def _get_book_chunks(self, book_name):
        """Obtiene todos los chunks de un libro desde los metadatos"""
        return [chunk for chunk in self.vector_store.metadata if book_name in chunk['book']]
    
    def _create_summary_prompt(self, chapter_text, length="medium"):
        """Crea el prompt para generar el resumen"""
        length_instructions = {
            "short": "Resumen breve y conciso de los puntos más importantes (máximo 250 palabras).",
            "medium": "Resumen detallado con los puntos principales y ejemplos relevantes (500-700 palabras).",
            "long": "Resumen extenso que capture todos los detalles importantes, argumentos y ejemplos (más de 1000 palabras)."
        }
        
        instruction = length_instructions.get(length, length_instructions["medium"])
        
        prompt = f"""
        Necesito un resumen del siguiente capítulo. {instruction}
        
        CONTENIDO DEL CAPÍTULO:
        {chapter_text}
        
        INSTRUCCIONES:
        1. El resumen debe mantener la estructura lógica del capítulo.
        2. Debe incluir los conceptos clave, argumentos principales y conclusiones.
        3. Evita incluir información irrelevante o tangencial.
        4. El resumen debe ser comprensible por sí mismo.
        """
        
        return prompt
    
    def _create_comparison_prompt(self, chapters_info):
        """Crea el prompt para comparar capítulos"""
        sources_text = ""
        
        for i, info in enumerate(chapters_info):
            sources_text += f"""
            FUENTE {i+1} - Libro: {info['book']}, Capítulo: {info['chapter']}
            {info['text']}
            
            """
        
        prompt = f"""
        Necesito un análisis comparativo detallado de los siguientes capítulos/secciones:
        
        {sources_text}
        
        INSTRUCCIONES DE ANÁLISIS:
        1. Identifica los temas principales que se abordan en cada fuente.
        2. Analiza similitudes y diferencias en:
           - Argumentos y posiciones principales
           - Metodología o enfoques utilizados
           - Conclusiones o resultados
           - Terminología y conceptos clave
        3. Evalúa las fortalezas y debilidades relativas de cada capítulo.
        4. Identifica si hay información complementaria entre las fuentes.
        5. Concluye con una síntesis que integre las diferentes perspectivas.
        
        El análisis debe ser estructurado, objetivo y detallado, comparando sistemáticamente los aspectos relevantes.
        """
        
        return prompt