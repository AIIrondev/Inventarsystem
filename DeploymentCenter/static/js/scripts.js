chatBox = document.getElementById('chatBox');

function fetchMessages() {
    fetch('/messages')
        .then(response => response.json())
        .then(data => {
            chatBox.innerHTML = '';
            data.messages.forEach(msg => {
                const messageElement = document.createElement('div');
                messageElement.textContent = msg;
                chatBox.appendChild(messageElement);
            });
        });
}

setInterval(fetchMessages, 1000);