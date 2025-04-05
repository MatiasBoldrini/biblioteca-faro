document.addEventListener('DOMContentLoaded', function () {
    // Elementos DOM para pestañas
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // Selectores de libros y capítulos
    const bookSelector = document.getElementById('book-selector');
    const summaryBookSelector = document.getElementById('summary-book-selector');
    const chapterSelector = document.getElementById('chapter-selector');
    const summaryChapterSelector = document.getElementById('summary-chapter-selector');
    const summaryOptions = document.getElementById('summary-options');
    
    // Elementos para comparación
    const comparisonBookSelector = document.getElementById('comparison-book-selector');
    const comparisonChapterSelector = document.getElementById('comparison-chapter-selector');
    const addComparisonChapterBtn = document.getElementById('add-comparison-chapter');
    const selectedChaptersContainer = document.getElementById('selected-chapters');
    const generateComparisonBtn = document.getElementById('generate-comparison');
    
    // Elementos para resumen
    const summaryLengthOptions = document.querySelectorAll('.summary-option');
    const generateSummaryBtn = document.getElementById('generate-summary');
    
    // Modales
    const summaryModal = document.getElementById('summary-modal');
    const comparisonModal = document.getElementById('comparison-modal');
    const closeBtns = document.querySelectorAll('.close');
    
    // Variables de estado
    let books = [];
    let currentChapters = {};
    let selectedChaptersForComparison = [];
    let selectedSummaryLength = 'short';
    
    // Manejo de pestañas
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            
            // Actualizar clase activa en botones
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // Mostrar contenido de pestaña correspondiente
            tabContents.forEach(tab => {
                if (tab.id === tabId + '-tab') {
                    tab.classList.add('active');
                } else {
                    tab.classList.remove('active');
                }
            });
        });
    });
    
    // Cargar lista de libros al iniciar
    function loadBooks() {
        fetch('/documents')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.documents && data.documents.length > 0) {
                    books = data.documents;
                    
                    // Actualizar todos los selectores de libros
                    updateBookSelectors();
                } else {
                    console.log('No hay documentos disponibles');
                }
            })
            .catch(error => {
                console.error('Error al cargar documentos:', error);
                showNotification('Error al cargar la lista de documentos', 'error');
            });
    }
    
    // Actualizar todos los selectores de libros
    function updateBookSelectors() {
        const selectors = [bookSelector, summaryBookSelector, comparisonBookSelector];
        
        selectors.forEach(selector => {
            // Mantener solo la primera opción (placeholder)
            selector.innerHTML = '<option value="">Selecciona un libro</option>';
            
            // Agregar opciones de libros
            books.forEach(book => {
                const option = document.createElement('option');
                option.value = book.filename;
                option.textContent = book.filename.split('_')[0]; // Mostrar nombre sin UUID
                selector.appendChild(option);
            });
        });
    }
    
    // Cargar capítulos para un libro específico
    function loadChapters(bookName, targetSelector = 'chapter-list-container') {
        const container = document.getElementById(targetSelector);
        
        // Mostrar indicador de carga
        container.innerHTML = `
            <div class="text-center p-3">
                <div class="loading-spinner mx-auto mb-2"></div>
                <p class="text-muted">Identificando capítulos...</p>
            </div>
        `;
        
        fetch(`/books/${encodeURIComponent(bookName)}/chapters`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.chapters && data.chapters.length > 0) {
                    currentChapters[bookName] = data.chapters;
                    
                    if (targetSelector === 'chapter-list-container') {
                        // Mostrar lista de capítulos
                        displayChapterList(data.chapters, container);
                    } else if (targetSelector === 'summary-chapter-selector') {
                        // Actualizar selector de capítulos para resumen
                        updateChapterSelector(chapterSelector, data.chapters);
                        document.getElementById(targetSelector).classList.remove('d-none');
                    } else if (targetSelector === 'comparison-chapter-selector') {
                        // Actualizar selector de capítulos para comparación
                        updateChapterSelector(comparisonChapterSelector, data.chapters);
                    }
                } else {
                    container.innerHTML = `
                        <p class="text-muted text-center">
                            <i class="fas fa-info-circle fs-4 d-block mb-2"></i>
                            No se encontraron capítulos en este documento
                        </p>
                    `;
                }
            })
            .catch(error => {
                console.error('Error al cargar capítulos:', error);
                container.innerHTML = `
                    <p class="text-danger text-center">
                        <i class="fas fa-exclamation-circle fs-4 d-block mb-2"></i>
                        Error al identificar capítulos
                    </p>
                `;
                showNotification('Error al cargar capítulos', 'error');
            });
    }
    
    // Mostrar lista de capítulos
    function displayChapterList(chapters, container) {
        if (chapters.length === 0) {
            container.innerHTML = '<p class="text-center">No se encontraron capítulos</p>';
            return;
        }
        
        const listHtml = `
            <ul class="chapter-list">
                ${chapters.map(chapter => `
                    <li class="chapter-item">
                        <div>
                            <div class="chapter-title">${chapter.title}</div>
                            <div class="chapter-page">Página: ${chapter.page}</div>
                        </div>
                        <div class="chapter-actions">
                            <button class="btn btn-sm btn-outline-primary summary-btn" 
                                    data-chapter="${chapter.chapter_number}">
                                <i class="fas fa-file-alt"></i>
                            </button>
                        </div>
                    </li>
                `).join('')}
            </ul>
        `;
        
        container.innerHTML = listHtml;
        
        // Agregar listeners a los botones de resumen
        container.querySelectorAll('.summary-btn').forEach(button => {
            button.addEventListener('click', function() {
                const chapterNum = this.getAttribute('data-chapter');
                const bookName = bookSelector.value;
                generateChapterSummary(bookName, chapterNum);
            });
        });
    }
    
    // Actualizar selector de capítulos
    function updateChapterSelector(selector, chapters) {
        selector.innerHTML = '<option value="">Selecciona un capítulo</option>';
        
        chapters.forEach(chapter => {
            const option = document.createElement('option');
            option.value = chapter.chapter_number;
            option.textContent = `Capítulo ${chapter.chapter_number}: ${limitText(chapter.title, 40)}`;
            selector.appendChild(option);
        });
    }
    
    // Generar resumen de capítulo
    function generateChapterSummary(bookName, chapterNum, length = 'medium') {
        // Mostrar indicador de carga
        document.querySelector('#summary-modal .summary-content').innerHTML = `
            <div class="text-center p-3">
                <div class="loading-spinner mx-auto mb-3"></div>
                <p>Generando resumen...</p>
            </div>
        `;
        
        // Establecer título en el modal
        const bookDisplayName = bookName.split('_')[0]; // Quitar UUID
        document.querySelector('#summary-modal .summary-title').textContent = 
            `Resumen: ${bookDisplayName} - Capítulo ${chapterNum}`;
        
        // Mostrar modal
        summaryModal.style.display = 'block';
        
        // Hacer petición al servidor
        fetch(`/books/${encodeURIComponent(bookName)}/chapters/${encodeURIComponent(chapterNum)}/summary?length=${length}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.querySelector('#summary-modal .summary-content').innerHTML = formatText(data.summary);
                } else {
                    document.querySelector('#summary-modal .summary-content').innerHTML = `
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            ${data.message || 'Error al generar el resumen'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error al generar resumen:', error);
                document.querySelector('#summary-modal .summary-content').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Error al generar el resumen. Inténtalo de nuevo más tarde.
                    </div>
                `;
            });
    }
    
    // Comparar capítulos
    function compareChapters() {
        if (selectedChaptersForComparison.length < 2) {
            showNotification('Se necesitan al menos 2 capítulos para comparar', 'warning');
            return;
        }
        
        // Mostrar indicador de carga
        document.querySelector('#comparison-modal .comparison-content').innerHTML = `
            <div class="text-center p-3">
                <div class="loading-spinner mx-auto mb-3"></div>
                <p>Comparando capítulos...</p>
            </div>
        `;
        
        // Mostrar modal
        comparisonModal.style.display = 'block';
        
        // Hacer petición al servidor
        fetch('/compare-chapters', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ sources: selectedChaptersForComparison })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.querySelector('#comparison-modal .comparison-content').innerHTML = formatText(data.comparison);
                } else {
                    document.querySelector('#comparison-modal .comparison-content').innerHTML = `
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            ${data.message || 'Error al realizar la comparación'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error al comparar:', error);
                document.querySelector('#comparison-modal .comparison-content').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Error al realizar la comparación. Inténtalo de nuevo más tarde.
                    </div>
                `;
            });
    }
    
    // Agregar capítulo seleccionado a la lista de comparación
    function addChapterToComparison() {
        const bookName = comparisonBookSelector.value;
        const chapterNum = comparisonChapterSelector.value;
        
        if (!bookName || !chapterNum) {
            showNotification('Selecciona un libro y un capítulo', 'warning');
            return;
        }
        
        // Verificar si ya está añadido
        const alreadyExists = selectedChaptersForComparison.some(
            item => item.book === bookName && item.chapter === chapterNum
        );
        
        if (alreadyExists) {
            showNotification('Este capítulo ya ha sido añadido', 'warning');
            return;
        }
        
        // Agregar a la lista de seleccionados
        selectedChaptersForComparison.push({
            book: bookName,
            chapter: chapterNum
        });
        
        // Actualizar UI
        updateSelectedChaptersUI();
    }
    
    // Actualizar la UI de capítulos seleccionados
    function updateSelectedChaptersUI() {
        if (selectedChaptersForComparison.length === 0) {
            selectedChaptersContainer.innerHTML = '';
            generateComparisonBtn.classList.add('d-none');
            return;
        }
        
        let html = '';
        selectedChaptersForComparison.forEach((item, index) => {
            const bookDisplay = item.book.split('_')[0]; // Quitar UUID
            html += `
                <div class="selected-chapter">
                    ${bookDisplay} - Cap. ${item.chapter}
                    <i class="fas fa-times remove-chapter" data-index="${index}"></i>
                </div>
            `;
        });
        
        selectedChaptersContainer.innerHTML = html;
        
        // Mostrar botón de comparar si hay al menos 2 capítulos
        if (selectedChaptersForComparison.length >= 2) {
            generateComparisonBtn.classList.remove('d-none');
        } else {
            generateComparisonBtn.classList.add('d-none');
        }
        
        // Añadir eventos para eliminar capítulos
        document.querySelectorAll('.remove-chapter').forEach(button => {
            button.addEventListener('click', function() {
                const index = parseInt(this.getAttribute('data-index'));
                selectedChaptersForComparison.splice(index, 1);
                updateSelectedChaptersUI();
            });
        });
    }
    
    // Formatear texto (párrafos)
    function formatText(text) {
        if (!text) return '';
        
        return text
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^(.+?)$/, '<p>$1</p>');
    }
    
    // Limitar texto a cierta longitud
    function limitText(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
    
    // Event Listeners
    
    // Selector de libro (lista de capítulos)
    bookSelector.addEventListener('change', function() {
        const bookName = this.value;
        if (bookName) {
            loadChapters(bookName);
        } else {
            document.getElementById('chapter-list-container').innerHTML = `
                <p class="text-muted text-center">
                    <i class="fas fa-list fs-4 d-block mb-2"></i>
                    Selecciona un libro para ver sus capítulos
                </p>
            `;
        }
    });
    
    // Selector de libro (resumen)
    summaryBookSelector.addEventListener('change', function() {
        const bookName = this.value;
        if (bookName) {
            loadChapters(bookName, 'summary-chapter-selector');
        } else {
            summaryChapterSelector.classList.add('d-none');
            summaryOptions.classList.add('d-none');
        }
    });
    
    // Selector de capítulo (resumen)
    chapterSelector.addEventListener('change', function() {
        if (this.value) {
            summaryOptions.classList.remove('d-none');
        } else {
            summaryOptions.classList.add('d-none');
        }
    });
    
    // Selector de libro (comparación)
    comparisonBookSelector.addEventListener('change', function() {
        const bookName = this.value;
        if (bookName) {
            loadChapters(bookName, 'comparison-chapter-selector');
        } else {
            comparisonChapterSelector.innerHTML = '<option value="">Selecciona un capítulo</option>';
        }
    });
    
    // Botón para añadir capítulo a comparación
    addComparisonChapterBtn.addEventListener('click', addChapterToComparison);
    
    // Opciones de longitud de resumen
    summaryLengthOptions.forEach(option => {
        option.addEventListener('click', function() {
            summaryLengthOptions.forEach(opt => opt.classList.remove('active'));
            this.classList.add('active');
            selectedSummaryLength = this.getAttribute('data-length');
        });
    });
    
    // Botón generar resumen
    generateSummaryBtn.addEventListener('click', function() {
        const bookName = summaryBookSelector.value;
        const chapterNum = chapterSelector.value;
        
        if (!bookName || !chapterNum) {
            showNotification('Selecciona un libro y un capítulo', 'warning');
            return;
        }
        
        generateChapterSummary(bookName, chapterNum, selectedSummaryLength);
    });
    
    // Botón generar comparación
    generateComparisonBtn.addEventListener('click', compareChapters);
    
    // Cerrar modales
    closeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            summaryModal.style.display = 'none';
            comparisonModal.style.display = 'none';
        });
    });
    
    window.addEventListener('click', function(event) {
        if (event.target === summaryModal) {
            summaryModal.style.display = 'none';
        }
        if (event.target === comparisonModal) {
            comparisonModal.style.display = 'none';
        }
    });
    
    // Cargar libros al iniciar
    loadBooks();
    
    // Función de notificación (reutiliza la del chat.js)
    function showNotification(message, type = 'info') {
        // Si existe la función global, la utiliza
        if (window.showNotification) {
            window.showNotification(message, type);
            return;
        }
        
        // Si no existe, crea una implementación básica
        const toast = document.createElement('div');
        toast.className = `toast toast-${type} show`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="${getToastIcon(type)}"></i>
                <span class="toast-message">${message}</span>
            </div>
        `;
        
        // Si no existe el contenedor, lo crea
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.style.position = 'fixed';
            toastContainer.style.bottom = '20px';
            toastContainer.style.right = '20px';
            toastContainer.style.zIndex = '9999';
            document.body.appendChild(toastContainer);
        }
        
        toastContainer.appendChild(toast);
        
        // Eliminar toast después de 3 segundos
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    function getToastIcon(type) {
        switch (type) {
            case 'success': return 'fas fa-check-circle';
            case 'error': return 'fas fa-exclamation-circle';
            case 'warning': return 'fas fa-exclamation-triangle';
            default: return 'fas fa-info-circle';
        }
    }
});