import os
import re
import json
from typing import Dict, List

import google.generativeai as genai
from dotenv import load_dotenv

from .vector_store_service import VectorStoreService
from .chapter_service import ChapterService

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

class GeminiService:
    def __init__(self, vector_store=None, chapter_service=None, document_service=None):
        """
        Initialize the Gemini service with API key from environment
        
        Args:
            vector_store: Instancia existente de VectorStoreService
            chapter_service: Instancia existente de ChapterService
            document_service: Instancia existente de DocumentService
        """
        # Configure the Gemini API
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        
        # Get available models
        try:
            self.model = genai.GenerativeModel(
                'models/gemini-1.5-pro',
                generation_config={'temperature': 0.3, 'top_p': 0.7}
            )
            
            # Modelo específico para la detección de intenciones con temperatura más baja
            self.intent_model = genai.GenerativeModel(
                'models/gemini-1.5-pro',
                generation_config={'temperature': 0.1, 'top_p': 0.95}
            )
            
            print("Successfully connected to Gemini API")
        except Exception as e:
            print(f"Error connecting to Gemini API: {e}")
            raise
        
        self.relevance_wall = 0.4
        
        # Usar servicios existentes o crear nuevos si no se proporcionan
        self.vector_store = vector_store if vector_store is not None else VectorStoreService()
        self.document_service = document_service
        
        # La instancia de chapter_service se asignará más tarde desde app.py después de crear ambos servicios
        self.chapter_service = chapter_service
        
    def set_chapter_service(self, chapter_service):
        """Establece el servicio de capítulos después de la inicialización"""
        self.chapter_service = chapter_service
    
    def set_document_service(self, document_service):
        """Establece el servicio de documentos después de la inicialización"""
        self.document_service = document_service
        
    def generate_response(self, query: str, context: str, sources: List[Dict]) -> str:
        """
        Generate a response using Gemini based on the query and context
        
        Args:
            query: User's question
            context: Text content from relevant chunks
            sources: List of source metadata for citation
        
        Returns:
            Generated response with citations
        """
        # Primero detectamos si es una solicitud especial (resumen o comparación)
        # Usamos detección basada en Gemini en lugar de expresiones regulares
        intent_detection = self._detect_intent_with_gemini(query)
        
        if intent_detection.get('is_special_request') and self.chapter_service is not None:
            if intent_detection['intent'] == 'summarize_chapter':
                return self._handle_chapter_summary_request(query, intent_detection)
            elif intent_detection['intent'] == 'compare_chapters':
                return self._handle_chapter_comparison_request(query, intent_detection)
        
        try:
            if not sources or not any(source['score'] > self.relevance_wall for source in sources):
                return "No encontré información suficientemente relevante para responder a tu pregunta específica. ¿Podrías reformularla o ser más específico?"

            # Crear un diccionario para agrupar fuentes por libro y página
            grouped_sources = {}
            for i, source in enumerate(sources):
                if source['score'] > self.relevance_wall:
                    book_name = source["book"].split("_")[0]
                    page_num = source["page"]
                    key = f"{book_name}_{page_num}"
                    print(f"\n {'-'*30}\n Source {i}: {source['score']}\n {'-'*30} \n - {source['text']}")
                    if key not in grouped_sources:
                        grouped_sources[key] = {
                            'index': len(grouped_sources) + 1,
                            'book': book_name,
                            'page': page_num,
                            'text': source['text'].strip()
                        }

            # Formatear el contexto usando las fuentes agrupadas
            formatted_sources = []
            for source_info in grouped_sources.values():
                formatted_sources.append(
                    f"[Source {source_info['index']}] From '{source_info['book']}', "
                    f"page {int(source_info['page']) + 1}:\n{source_info['text']}"
                )
            
            formatted_context = "\n\n".join(formatted_sources)
            print(f"Formatted context:\n{formatted_context}")
            prompt = f"""
            You are a technical assistant. Use ONLY the provided sources to answer the question.
            
            DOCUMENTATION CONTEXT:
            {formatted_context}
            
            USER QUESTION:
            {query}
            
            INSTRUCTIONS:
            1. Answer in detail using ALL RELEVANT SOURCES.
            2. For every claim, cite the source like [Source Number].
            3. If sources conflict, explain differences clearly.
            4. List all used sources with sources numbers, book name and page numbers at the end.
            5. If there are differences between sources, explain them. in a special section.

            """
            
            # Generate response
            response = self.model.generate_content(prompt)
            answer = response.text
            
            # Process the answer to add proper citation links
            answer = self._format_citations(answer, list(grouped_sources.values()))
            
            return answer
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return f"Lo siento, ocurrió un error al generar la respuesta: {str(e)}"
    
    def _get_available_books(self):
        """Obtiene la lista de libros disponibles en el sistema"""
        available_books = []
        
        # Si tenemos acceso al document_service, lo usamos
        if self.document_service:
            try:
                for file_path in self.document_service.get_all_books():
                    filename = os.path.basename(file_path)
                    # Extraer el nombre del libro (sin UUID)
                    book_name = filename.split("_")[0]
                    available_books.append({
                        "full_name": filename,
                        "name": book_name
                    })
            except Exception as e:
                print(f"Error al obtener libros desde document_service: {e}")
        
        # Como respaldo, también revisamos los metadatos del vector_store
        if not available_books and self.vector_store:
            try:
                books_set = set()
                for item in self.vector_store.metadata:
                    if 'book' in item:
                        book_full = item['book']
                        book_name = book_full.split("_")[0]
                        if book_full not in books_set:
                            books_set.add(book_full)
                            available_books.append({
                                "full_name": book_full,
                                "name": book_name
                            })
            except Exception as e:
                print(f"Error al obtener libros desde vector_store: {e}")
        
        return available_books
    
    def _detect_intent_with_gemini(self, query):
        """
        Utiliza Gemini para detectar la intención del usuario y los parámetros necesarios
        """
        # Obtener la lista de libros disponibles
        available_books = self._get_available_books()
        book_names = [book["name"] for book in available_books]
        book_full_names = [book["full_name"] for book in available_books]
        
        # Preparar el prompt para Gemini
        intent_prompt = f"""
        Analiza la siguiente consulta y determina qué acción está solicitando el usuario.
        
        CONSULTA DEL USUARIO:
        {query}
        
        LIBROS DISPONIBLES:
        {", ".join(book_names)}
        
        NOMBRES COMPLETOS DE ARCHIVOS:
        {", ".join(book_full_names)}
        
        Analiza si el usuario quiere:
        1. Resumir un capítulo específico de un libro.
        2. Comparar capítulos (del mismo libro o de diferentes libros).
        3. Hacer una consulta general (buscar información).

        Para cada tipo de consulta, extrae los parámetros relevantes:
        - Resumir: libro (nombre completo del archivo que mejor coincida), número de capítulo, longitud del resumen (corto, medio o largo)
        - Comparar: libros y capítulos a comparar (como pares de libro-capítulo)
        - Consulta general: no se necesitan parámetros adicionales

        IMPORTANTE: Si el usuario menciona un libro, usa fuzzy matching para encontrar el libro más parecido entre los disponibles.

        Responde en formato JSON con este formato:
        ```json
        {
          "is_special_request": true|false,
          "intent": "summarize_chapter"|"compare_chapters"|"general_query",
          "params": {
            // Para resumir:
            "book": "nombre_completo_del_archivo",
            "chapter": "número_o_id_del_capítulo",
            "length": "short|medium|long",
            
            // Para comparar:
            "sources": [
              {"book": "nombre_completo_del_archivo1", "chapter": "capítulo1"},
              {"book": "nombre_completo_del_archivo2", "chapter": "capítulo2"}
            ]
          }
        }
        ```
        
        Devuelve SOLO el objeto JSON sin explicaciones adicionales.
        """
        
        try:
            # Llamada a Gemini para determinar la intención
            response = self.intent_model.generate_content(intent_prompt)
            response_text = response.text.strip()
            
            # Extraer el JSON de la respuesta
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            intent_data = json.loads(response_text)
            
            # Validación básica del resultado
            if "is_special_request" not in intent_data or "intent" not in intent_data:
                print("Formato de respuesta de detección de intención inválido")
                return {"is_special_request": False, "intent": "general_query", "params": {}}
                
            return intent_data
            
        except Exception as e:
            print(f"Error en detección de intención con Gemini: {e}")
            # En caso de error, devolver intención genérica
            return {"is_special_request": False, "intent": "general_query", "params": {}}
    
    def _handle_chapter_summary_request(self, query, intent_data):
        """Maneja la generación de resumen de capítulo basado en la intención detectada"""
        if not self.chapter_service:
            return "El servicio de capítulos no está disponible en este momento."
        
        # Extraer parámetros según el nuevo formato
        book_name = intent_data['params'].get('book', '')
        chapter_num = intent_data['params'].get('chapter', '')
        summary_length = intent_data['params'].get('length', 'medium')
        
        if not book_name or not chapter_num:
            return "No pude entender qué capítulo o libro quieres resumir. Por favor, especifica el capítulo y el libro más claramente."
        
        # Ya tenemos el nombre completo del libro desde la detección de Gemini
        selected_book = book_name
        
        # Si no encontramos un libro exacto, buscamos por similitud en el vector store
        if not any(book['full_name'] == selected_book for book in self._get_available_books()):
            matching_books = []
            for file_path in self.vector_store.metadata:
                if 'book' in file_path and book_name.lower() in file_path['book'].lower():
                    if file_path['book'] not in matching_books:
                        matching_books.append(file_path['book'])
            
            if matching_books:
                selected_book = matching_books[0]
            else:
                return f"No encontré ningún libro que coincida con '{book_name}'. Verifica que el libro esté cargado en el sistema."
        
        # Generar resumen usando el servicio de capítulos
        try:
            result = self.chapter_service.summarize_chapter(selected_book, chapter_num, summary_length)
            
            if result["success"]:
                return f"📚 **Resumen del Capítulo {chapter_num} de {selected_book.split('_')[0]}**\n\n{result['summary']}"
            else:
                return f"No pude generar el resumen: {result['message']}"
                
        except Exception as e:
            return f"Ocurrió un error al generar el resumen: {str(e)}"
    
    def _handle_chapter_comparison_request(self, query, intent_data):
        """Maneja la comparación de capítulos basado en la intención detectada"""
        if not self.chapter_service:
            return "El servicio de capítulos no está disponible en este momento."
        
        # Extraer los pares de libro-capítulo según el nuevo formato
        sources = intent_data['params'].get('sources', [])
        
        if len(sources) < 2:
            return "Se necesitan al menos dos capítulos para hacer una comparación. Por favor, especifica los capítulos y libros a comparar."
            
        # Los libros ya vienen identificados por la detección de intención con Gemini
        
        # Generar la comparación
        try:
            result = self.chapter_service.compare_chapters(sources)
            
            if result["success"]:
                sources_text = ', '.join([f"Capítulo {s['chapter']} de {s['book'].split('_')[0]}" for s in sources])
                return f"🔄 **Comparación de {sources_text}**\n\n{result['comparison']}"
            else:
                return f"No pude realizar la comparación: {result['message']}"
                
        except Exception as e:
            return f"Ocurrió un error al comparar los capítulos: {str(e)}"
    
    def _format_citations(self, text: str, sources: List[Dict]) -> str:
        """Format the citations in the text with proper links to sources"""
        citation_pattern = r'\[Source (\d+)\]'
        
        processed_text = text
        
        # Create source mapping
        source_map = {
            str(source['index']): {
                "book": source["book"],
                "page": source["page"],
                "idx": idx
            } for idx, source in enumerate(sources)
        }
        
        # Replace citations with clickable spans
        for match in re.finditer(citation_pattern, text):
            citation_num = match.group(1)
            if citation_num in source_map:
                source = source_map[citation_num]
                replacement = f'<span class="citation" data-source-idx="{source["idx"]}">[Source {citation_num}]</span>'
                processed_text = processed_text.replace(match.group(0), replacement)
        
        return processed_text
    
    def process_file(self, file_path):
        """Process a newly uploaded file and add it to the vector store"""
        try:
            self.vector_store.add_document(file_path)
            return True
        except Exception as e:
            print(f"Error processing file: {str(e)}")
            return False
