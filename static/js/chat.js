document.addEventListener('DOMContentLoaded', function () {
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const fileUpload = document.getElementById('file-upload');

    // Focus input when page loads
    userInput.focus();

    // Function to add a message to the chat
    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        messageDiv.classList.add(isUser ? 'user-message' : 'bot-message');

        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');
        messageContent.textContent = content;

        messageDiv.appendChild(messageContent);
        chatMessages.appendChild(messageDiv);

        // Animate scroll to the bottom
        smoothScrollToBottom(chatMessages);
    }

    // Smooth scroll function
    function smoothScrollToBottom(element) {
        const targetPosition = element.scrollHeight;
        const startPosition = element.scrollTop;
        const distance = targetPosition - startPosition;
        const duration = 300;
        let startTime = null;

        function animation(currentTime) {
            if (startTime === null) startTime = currentTime;
            const timeElapsed = currentTime - startTime;
            const scrollY = easeInOutQuad(timeElapsed, startPosition, distance, duration);
            element.scrollTop = scrollY;

            if (timeElapsed < duration) {
                requestAnimationFrame(animation);
            }
        }

        function easeInOutQuad(t, b, c, d) {
            t /= d / 2;
            if (t < 1) return c / 2 * t * t + b;
            t--;
            return -c / 2 * (t * (t - 2) - 1) + b;
        }

        requestAnimationFrame(animation);
    }

    // Function to send message to the server
    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessage(message, true);

        // Clear input field
        userInput.value = '';

        try {
            // Add loading indicator
            const loadingDiv = document.createElement('div');
            loadingDiv.classList.add('message', 'bot-message');
            loadingDiv.innerHTML = '<div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>';
            chatMessages.appendChild(loadingDiv);

            // Smooth scroll to the loading indicator
            smoothScrollToBottom(chatMessages);

            // Send message to server
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: message })
            });

            // Remove loading indicator
            chatMessages.removeChild(loadingDiv);

            if (!response.ok) {
                throw new Error('Error al obtener respuesta del servidor');
            }

            const data = await response.json();

            // Add bot response to chat
            addMessage(data.response);

        } catch (error) {
            console.error('Error:', error);
            addMessage('Lo siento, hubo un error al procesar tu solicitud. Por favor, inténtalo de nuevo.', false);
        }

        // Focus back on input
        userInput.focus();
    }

    // Function to handle file upload
    async function handleFileUpload(file) {
        if (!file) return;

        try {
            // Create a FormData object to send the file
            const formData = new FormData();
            formData.append('file', file);

            // Add a message showing the file is being uploaded
            addMessage(`Subiendo archivo: ${file.name}`, true);

            // Add loading indicator
            const loadingDiv = document.createElement('div');
            loadingDiv.classList.add('message', 'bot-message');
            loadingDiv.innerHTML = '<div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>';
            chatMessages.appendChild(loadingDiv);

            // Send the file to server
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            // Remove loading indicator
            chatMessages.removeChild(loadingDiv);

            if (!response.ok) {
                throw new Error('Error al subir el archivo');
            }

            const data = await response.json();

            // Display server response
            addMessage(data.message);

        } catch (error) {
            console.error('Error al subir archivo:', error);
            addMessage('Lo siento, hubo un error al subir el archivo. Por favor, inténtalo de nuevo.', false);
        }
    }

    // Event listeners
    sendButton.addEventListener('click', sendMessage);

    userInput.addEventListener('keypress', function (event) {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });

    // File upload event listener
    fileUpload.addEventListener('change', function () {
        if (this.files && this.files.length > 0) {
            handleFileUpload(this.files[0]);
        }
    });

    // Disable form submission
    document.addEventListener('submit', function (event) {
        event.preventDefault();
    });
});
