# Biblioteca Faro

Biblioteca Faro es un sistema de biblioteca digital inteligente que permite cargar documentos, indexarlos y hacer consultas utilizando inteligencia artificial.

## Características

- Carga y procesamiento de documentos PDF, TXT, DOC y DOCX
- Extracción de texto con preservación de metadatos (páginas)
- Búsqueda semántica mediante embeddings y FAISS
- Generación de respuestas utilizando Google Gemini
- Interfaz web amigable

## Requisitos

- Python 3.9+ 
- Dependencias especificadas en `requirements.txt`
- API Key de Google Gemini
- Tesseract OCR (opcional, para mejorar la extracción de texto de PDF escaneados)

## Instalación

1. Clona el repositorio:
   ```
   git clone https://github.com/tu_usuario/biblioteca_faro.git
   ```

2. Instala las dependencias:
   ```
   pip install -r requirements.txt
   ```

3. Obtén una clave API de Gemini desde [Google AI Studio](https://makersuite.google.com/).

4. Crea un archivo `.env` en la raíz del proyecto y añade tu clave API:
   ```
   GOOGLE_API_KEY=tu_clave_api_aquí
   ```

5. Ejecuta la aplicación:
   ```
   python app.py
   ```

6. Abre tu navegador y dirígete a `http://localhost:5000`

## Estructura del Proyecto

- `app.py`: Aplicación principal de Flask
- `services/gemini_service.py`: Servicio para interactuar con la API de Gemini
- `templates/`: Contiene las plantillas HTML
- `static/`: Contiene archivos CSS y JavaScript
- `uploads/`: Carpeta donde se almacenan los documentos subidos

## Funcionalidades

- Interfaz de chat intuitiva
- Capacidad para subir documentos (PDF, TXT, DOC, DOCX)
- Consultas inteligentes utilizando Google Gemini AI
