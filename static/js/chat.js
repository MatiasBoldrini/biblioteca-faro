document.addEventListener('DOMContentLoaded', function () {
    const chatContainer = document.getElementById('chatContainer');
    const queryInput = document.getElementById('queryInput');
    const sendButton = document.getElementById('sendButton');
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressBar = uploadProgress.querySelector('.progress-bar');
    const uploadStatus = document.getElementById('uploadStatus');
    const reindexButton = document.getElementById('reindexButton');
    const querySpinner = document.getElementById('querySpinner');

    // Handle file upload by clicking
    uploadArea.addEventListener('click', function () {
        fileInput.click();
    });

    // Handle file upload by drag and drop
    uploadArea.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadArea.classList.add('active');
    });

    uploadArea.addEventListener('dragleave', function () {
        uploadArea.classList.remove('active');
    });

    uploadArea.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadArea.classList.remove('active');

        if (e.dataTransfer.files.length) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    // Handle file input change
    fileInput.addEventListener('change', function () {
        if (fileInput.files.length) {
            handleFileUpload(fileInput.files[0]);
        }
    });

    // Handle file upload
    function handleFileUpload(file) {
        const allowedTypes = [
            'application/pdf',
            'text/plain',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ];

        if (!allowedTypes.includes(file.type)) {
            showNotification('Formato no soportado. Solo se permiten PDF, TXT, DOC y DOCX.', 'error');
            return;
        }

        // Show progress
        uploadProgress.classList.remove('d-none');
        uploadStatus.innerText = 'Subiendo archivo...';
        progressBar.style.width = '0%';

        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();

        // Track upload progress
        xhr.upload.addEventListener('progress', function (e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progressBar.style.width = percentComplete + '%';
            }
        });

        // Handle response
        xhr.onload = function () {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                uploadStatus.innerText = response.message;
                showNotification(`¡Archivo "${response.filename}" subido con éxito!`, 'success');

                // Add assistant message about successful upload
                const messageDiv = document.createElement('div');
                messageDiv.className = 'assistant-message';
                messageDiv.innerHTML = `<p>He procesado el documento "<strong>${response.filename}</strong>".</p><p>¡Pregúntame sobre su contenido!</p>`;
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;

                // Update document list
                updateDocumentList();
            } else {
                try {
                    const response = JSON.parse(xhr.responseText);
                    uploadStatus.innerText = 'Error: ' + response.message;
                    showNotification('Error: ' + response.message, 'error');
                } catch (e) {
                    uploadStatus.innerText = 'Error al procesar el archivo.';
                    showNotification('Error al procesar el archivo', 'error');
                }
            }
        };

        xhr.onerror = function () {
            uploadStatus.innerText = 'Error en la conexión.';
            showNotification('Error en la conexión', 'error');
        };

        // Send request
        xhr.open('POST', '/upload', true);
        xhr.send(formData);
    }

    // Handle query submission
    sendButton.addEventListener('click', function () {
        sendQuery();
    });

    queryInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            sendQuery();
        }
    });

    function sendQuery() {
        const query = queryInput.value.trim();
        if (!query) return;

        // Show user message
        const userMessageDiv = document.createElement('div');
        userMessageDiv.className = 'user-message';
        userMessageDiv.innerText = query;
        chatContainer.appendChild(userMessageDiv);

        // Clear input
        queryInput.value = '';

        // Show loading indicator
        querySpinner.classList.remove('d-none');
        sendButton.disabled = true;

        // Add typing indicator
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'assistant-message typing-indicator';
        typingIndicator.innerHTML = `
            <span></span>
            <span></span>
            <span></span>
        `;
        chatContainer.appendChild(typingIndicator);

        // Scroll to bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;

        // Send query to server
        fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: query }),
        })
            .then(response => {
                if (!response.ok) {
                    // Intentar obtener el mensaje de error del servidor
                    return response.json().then(errData => {
                        throw new Error(errData.message || `Error ${response.status}: ${response.statusText}`);
                    }).catch(err => {
                        // Si no se puede parsear la respuesta, usar mensaje genérico
                        throw new Error(`Error ${response.status}: No hay documentos indexados o el servidor no responde correctamente`);
                    });
                }
                return response.json();
            })
            .then(data => {
                // Remove typing indicator
                chatContainer.removeChild(typingIndicator);

                if (!data || !data.answer) {
                    throw new Error('La respuesta del servidor está vacía o en formato incorrecto');
                }

                // Create assistant message
                const assistantMessageDiv = document.createElement('div');
                assistantMessageDiv.className = 'assistant-message';
                assistantMessageDiv.innerHTML = formatAnswer(data.answer);

                // Add citation click handlers after the message is added to DOM
                chatContainer.appendChild(assistantMessageDiv);

                if (data.chunks && data.chunks.length > 0) {
                    // Add click handlers for citations
                    const citations = assistantMessageDiv.querySelectorAll('.citation');
                    citations.forEach(citation => {
                        citation.addEventListener('click', function () {
                            const sourceIdx = this.getAttribute('data-source-idx');
                            if (sourceIdx !== null && data.chunks && data.chunks[sourceIdx]) {
                                const source = data.chunks[sourceIdx];
                                showSourcePopup(source);
                            }
                        });
                    });
                }

                // Scroll to bottom
                chatContainer.scrollTop = chatContainer.scrollHeight;
            })
            .catch(error => {
                console.error('Error:', error);
                // Remove typing indicator
                chatContainer.removeChild(typingIndicator);

                const errorDiv = document.createElement('div');
                errorDiv.className = 'assistant-message error';
                errorDiv.innerHTML = `
                    <p class="error-message">
                        <i class="fas fa-exclamation-triangle text-warning me-2"></i>
                        ${error.message || 'Lo siento, ha ocurrido un error al procesar tu consulta. Por favor, verifica que haya documentos indexados y vuelve a intentar.'}
                    </p>
                    <p class="error-suggestion">
                        Sugerencias:
                        <ul>
                            <li>Verifica que haya documentos cargados en el sistema</li>
                            <li>Intenta reindexar los documentos usando el botón "Reindexar documentos"</li>
                            <li>Si el problema persiste, contacta al administrador</li>
                        </ul>
                    </p>
                `;
                chatContainer.appendChild(errorDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
                showNotification('Error al procesar la consulta: ' + error.message, 'error');
            })
            .finally(() => {
                // Hide loading indicator
                querySpinner.classList.add('d-none');
                sendButton.disabled = false;
            });
    }

    // Add new CSS for error messages
    const errorStyles = document.createElement('style');
    errorStyles.innerHTML = `
        .assistant-message.error {
            border-left: 4px solid #dc3545;
            background-color: rgba(220, 53, 69, 0.05);
            padding: 15px;
        }

        .error-message {
            color: #dc3545;
            font-weight: 500;
            margin-bottom: 10px;
        }

        .error-suggestion {
            font-size: 0.9em;
            color: #666;
        }

        .error-suggestion ul {
            margin-top: 5px;
            margin-bottom: 0;
            padding-left: 20px;
        }

        .error-suggestion li {
            margin-bottom: 5px;
        }
    `;
    document.head.appendChild(errorStyles);

    // Format the answer with better styling
    function formatAnswer(answer) {
        // Add some basic formatting if needed
        return answer
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^(.+?)$/, '<p>$1</p>');
    }

    // Show source information in a nicer way
    function showSourcePopup(source) {
        // Create a more elegant popup/toast (you can improve this)
        const sourceInfo = `Fuente: ${source.book}${source.page !== 'N/A' ? ', página ' + source.page : ''}`;
        showNotification(sourceInfo, 'info');
    }

    // Handle reindex button
    reindexButton.addEventListener('click', function () {
        if (confirm('¿Estás seguro de que deseas reindexar todos los documentos? Esta operación puede tomar tiempo.')) {
            reindexButton.disabled = true;
            reindexButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Reindexando...';

            fetch('/reindex', {
                method: 'POST'
            })
                .then(response => response.json())
                .then(data => {
                    showNotification(data.message, 'success');
                })
                .catch(error => {
                    console.error('Error:', error);
                    showNotification('Error al reindexar los documentos', 'error');
                })
                .finally(() => {
                    reindexButton.disabled = false;
                    reindexButton.innerHTML = '<i class="fas fa-sync-alt me-2"></i>Reindexar documentos';
                });
        }
    });

    // Crear el contenedor de toasts si no existe
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        document.body.appendChild(toastContainer);
    }

    // Modern notification function with glass effect
    function showNotification(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icon = getToastIcon(type);

        toast.innerHTML = `
            <div class="toast-content">
                <i class="${icon}"></i>
                <span class="toast-message">${message}</span>
            </div>
        `;

        toastContainer.appendChild(toast);

        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);

        // Remove toast after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    function getToastIcon(type) {
        switch (type) {
            case 'success':
                return 'fas fa-check-circle';
            case 'error':
                return 'fas fa-exclamation-circle';
            case 'warning':
                return 'fas fa-exclamation-triangle';
            default:
                return 'fas fa-info-circle';
        }
    }

    // Add CSS for toast notifications
    const toastStyles = document.createElement('style');
    toastStyles.innerHTML = `
        #toast-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
        }

        .toast {
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            padding: 12px 20px;
            margin-top: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transform: translateX(120%);
            transition: transform 0.3s ease;
            min-width: 200px;
            max-width: 350px;
        }

        .toast.show {
            transform: translateX(0);
        }

        .toast-content {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .toast-message {
            color: #333;
            font-size: 0.9rem;
        }

        .toast i {
            font-size: 1.2rem;
        }

        .toast-success i { color: #28a745; }
        .toast-error i { color: #dc3545; }
        .toast-warning i { color: #ffc107; }
        .toast-info i { color: #17a2b8; }

        @media (max-width: 480px) {
            #toast-container {
                bottom: 10px;
                right: 10px;
                left: 10px;
            }
            
            .toast {
                width: 100%;
            }
        }
    `;
    document.head.appendChild(toastStyles);

    // Function to update document list
    function updateDocumentList() {
        const documentList = document.getElementById('documentList');

        fetch('/documents')
            .then(response => response.json())
            .then(data => {
                if (data.documents && data.documents.length > 0) {
                    const listHtml = `
                        <ul class="list-group">
                            ${data.documents.map(doc => `
                                <li class="list-group-item d-flex justify-content-between align-items-center">
                                    <span>
                                        <i class="fas fa-file-alt me-2"></i>
                                        ${doc.filename}
                                    </span>
                                    <div>
                                        <small class="text-muted me-2">${formatFileSize(doc.size)}</small>
                                        <button class="btn btn-sm btn-outline-danger delete-doc" data-filename="${doc.filename}">
                                            <i class="fas fa-trash"></i>
                                        </button>
                                    </div>
                                </li>
                            `).join('')}
                        </ul>`;
                    documentList.innerHTML = listHtml;

                    // Add event listeners for delete buttons
                    documentList.querySelectorAll('.delete-doc').forEach(button => {
                        button.addEventListener('click', function () {
                            const filename = this.getAttribute('data-filename');
                            if (confirm(`¿Estás seguro de que deseas eliminar "${filename}"?`)) {
                                deleteDocument(filename);
                            }
                        });
                    });
                } else {
                    documentList.innerHTML = `
                        <p class="text-muted text-center">
                            <i class="fas fa-inbox fs-4 d-block mb-2"></i>
                            No hay documentos cargados
                        </p>`;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                documentList.innerHTML = `
                    <p class="text-danger text-center">
                        <i class="fas fa-exclamation-circle fs-4 d-block mb-2"></i>
                        Error al cargar los documentos
                    </p>`;
            });
    }

    function deleteDocument(filename) {
        fetch(`/documents/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        })
            .then(response => response.json())
            .then(data => {
                showNotification(data.message, 'success');
                updateDocumentList();
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Error al eliminar el documento', 'error');
            });
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Call updateDocumentList when the page loads
    updateDocumentList();

    // Add CSS class for typing indicator
    const style = document.createElement('style');
    style.innerHTML = `
        .typing-indicator {
            display: flex;
            align-items: center;
            column-gap: 6px;
            padding: 15px 20px;
        }
        .typing-indicator span {
            height: 8px;
            width: 8px;
            background-color: #aaa;
            display: block;
            border-radius: 50%;
            opacity: 0.4;
            animation: typing 1s infinite ease-in-out;
        }
        .typing-indicator span:nth-child(1) { animation-delay: 0s; }
        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0% { transform: translateY(0px); opacity: 0.4; }
            50% { transform: translateY(-5px); opacity: 0.8; }
            100% { transform: translateY(0px); opacity: 0.4; }
        }
    `;
    document.head.appendChild(style);
});
