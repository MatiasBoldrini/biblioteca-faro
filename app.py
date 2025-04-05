import os
import shutil
import tempfile
from pathlib import Path

from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.utils import secure_filename

from config.init_config import init_environment
from services.document_service import DocumentService
from services.gemini_service import GeminiService
from services.vector_store_service import VectorStoreService
from services.chapter_service import ChapterService

# Initialize environment before anything else
init_environment()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'biblioteca-faro-secret')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# Define allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx'}
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Inicialización única de servicios
print("Initializing services...")
# Inicializamos primero los servicios base
vector_store = VectorStoreService()
document_service = DocumentService()

# Inicializamos servicios que dependen de los anteriores
chapter_service = ChapterService(vector_store=vector_store)
gemini_service = GeminiService(vector_store=vector_store, document_service=document_service)

# Establecemos la referencia cruzada después de la creación
gemini_service.set_chapter_service(chapter_service)

print("Services initialized successfully")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        try:
            # Save file temporarily
            filename = secure_filename(file.filename)
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, filename)
            file.save(temp_path)
            
            # Process file
            processed_path = document_service.process_file(temp_path)
            
            # Add to vector store
            chunks_added = vector_store.add_document(processed_path)
            
            # Clean up temp file
            shutil.rmtree(temp_dir)
            
            return jsonify({
                'success': True,
                'message': f'File processed successfully. Added {chunks_added} chunks to the index.',
                'filename': filename
            })
        
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error processing file: {str(e)}'
            }), 500
    
    return jsonify({
        'success': False,
        'message': 'Invalid file type. Allowed types: PDF, TXT, DOC, DOCX'
    }), 400

@app.route('/query', methods=['POST'])
def query():
    data = request.get_json()
    user_query = data.get('query', '')
    
    if not user_query:
        return jsonify({
            'success': False,
            'message': 'Query cannot be empty'
        }), 400
    
    try:
        # Ahora usamos directamente Gemini para detectar la intención
        intent_detection = gemini_service._detect_intent_with_gemini(user_query)
        
        if intent_detection.get('is_special_request'):
            # Si es una solicitud de resumen o comparación, manejarlo directamente
            if intent_detection['intent'] == 'summarize_chapter':
                answer = gemini_service._handle_chapter_summary_request(user_query, intent_detection)
                return jsonify({
                    'success': True,
                    'answer': answer,
                    'chunks': []
                })
            elif intent_detection['intent'] == 'compare_chapters':
                answer = gemini_service._handle_chapter_comparison_request(user_query, intent_detection)
                return jsonify({
                    'success': True,
                    'answer': answer,
                    'chunks': []
                })
        
        # Si no es una solicitud especial, continuar con el flujo normal
        results = vector_store.search(user_query, top_k=5)
        
        if not results:
            return jsonify({
                'success': True,
                'answer': 'No encontré información relevante para responder a tu pregunta. Por favor, intenta reformular la pregunta o asegúrate de que la información esté en los documentos subidos.',
                'chunks': []
            })
        
        # Build context from chunks
        context = "\n\n".join([f"Fragmento de '{r['book']}'" + 
                              (f", página {r['page']}" if r['page'] != '-1' else "") + 
                              f": {r['text']}" for r in results])
        # Generate response using Gemini
        answer = gemini_service.generate_response(user_query, context, results)
        
        return jsonify({
            'success': True,
            'answer': answer,
            'chunks': results
        })
    
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error processing query: {str(e)}'
        }), 500

@app.route('/reindex', methods=['POST'])
def reindex():
    try:
        total_chunks = vector_store.reindex_all_documents()
        return jsonify({
            'success': True,
            'message': f'Reindexing complete. Total chunks: {total_chunks}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error during reindexing: {str(e)}'
        }), 500

@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        documents = []
        for file_path in document_service.get_all_books():
            file_stat = os.stat(file_path)
            documents.append({
                'filename': os.path.basename(file_path),
                'size': file_stat.st_size,
                'modified': file_stat.st_mtime
            })
        return jsonify({
            'success': True,
            'documents': documents
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error listing documents: {str(e)}'
        }), 500

@app.route('/documents/<filename>', methods=['DELETE'])
def delete_document(filename):
    try:
        file_path = os.path.join(document_service.books_dir, secure_filename(filename))
        if os.path.exists(file_path):
            os.remove(file_path)
            # Also remove from vector store
            vector_store.remove_document(filename)
            return jsonify({
                'success': True,
                'message': f'Document {filename} deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Document not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting document: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8500)))
