import os
import re
from typing import Dict, List

import google.generativeai as genai
from dotenv import load_dotenv

from .vector_store_service import VectorStoreService

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

class GeminiService:
    def __init__(self):
        """Initialize the Gemini service with API key from environment"""
        # Configure the Gemini API
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        
        # Get available models
        try:
            self.model = genai.GenerativeModel(
                'models/gemini-1.5-pro',
                generation_config={'temperature': 0.3, 'top_p': 0.7 }
            )
            print("Successfully connected to Gemini API")
        except Exception as e:
            print(f"Error connecting to Gemini API: {e}")
            raise
        self.relevance_wall = 0.4
        self.vector_store = VectorStoreService()
        
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
            
            # Add source list at the end if not present
            # if "Sources used:" not in answer:
            #     answer += "\n\nSources used:\n"
            #     for source_info in grouped_sources.values():
            #         answer += f"* [Source {source_info['index']}] from '{source_info['book']}', page {int(source_info['page']) + 1}\n"
            
            # Process the answer to add proper citation links
            answer = self._format_citations(answer, list(grouped_sources.values()))
            
            return answer
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return f"Lo siento, ocurrió un error al generar la respuesta: {str(e)}"
    
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
