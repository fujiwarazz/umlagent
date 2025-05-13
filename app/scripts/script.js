// const chatBox = document.getElementById('chatBox');
// const userInput = document.getElementById('userInput');
// const sendButton = document.getElementById('sendButton');

// // --- WebSocket Setup ---
// // WebSocket server address - must match your FastAPI endpoint
// const websocketUrl = `ws://localhost:8000/ws`;
// let websocket;
// // --- Chat UI Functions ---
// // Added typingEffect parameter
// async function appendMessage(text, sender, typingEffect = false) {
//     const messageElement = document.createElement('div');
//     messageElement.classList.add('message', sender + '-message'); // Add base message and sender classes

//     chatBox.appendChild(messageElement); // Append element first so we can type into it
//     //scrollToBottom(); // Scroll down to show the new message area

//     if (sender === 'agent' && typingEffect) {
//         // Apply typing effect for agent messages
//         const cursor = document.createElement('span');
//         cursor.classList.add('typing-cursor');
//         messageElement.appendChild(cursor); // Add cursor initially

//         for (let i = 0; i < text.length; i++) {
//             messageElement.insertBefore(document.createTextNode(text.charAt(i)), cursor); // Insert text before cursor
//             // Add a small delay for typing effect
//             await new Promise(resolve => setTimeout(resolve, 20)); // Adjust typing speed here
//           //  scrollToBottom(); // Keep scrolling as text is added
//         }
//         messageElement.removeChild(cursor); // Remove cursor after typing
//     } else {
//         // No typing effect, just set the text
//         messageElement.textContent = text;
//         //scrollToBottom(); // Scroll down after adding static text
//     }
// }

// function connectWebSocket() {
//     appendMessage("Connecting to the agent...", 'agent', true);
//     websocket = new WebSocket(websocketUrl);

//     websocket.onopen = function(event) {
//         console.log('WebSocket connection opened:', event);
//         // Use a more subtle connection message
//         // appendMessage("Connected to the agent.", 'agent', false); // Don't type initial message
//         sendButton.disabled = false; // Enable send button on connection
//         userInput.disabled = false;
//         userInput.focus(); // Focus input field
//         appendMessage("Connecting to the agent Successfully", 'agent', true);
//     };

//     websocket.onmessage = async function(event) { // Made async to use await for typing
//         console.log('Message from server:', event.data);
//         // Append agent message to the chat box with typing effect
//         await appendMessage(event.data, 'agent', true); // Enable typing effect
//        // scrollToBottom();
//     };

//     websocket.onerror = function(event) {
//         console.error('WebSocket error observed:', event);
//         appendMessage("Error connecting to agent. Please try again later.", 'agent', false); // No typing for errors
//         sendButton.disabled = true;
//         userInput.disabled = true;
//     };

//     websocket.onclose = function(event) {
//         console.log('WebSocket connection closed:', event);
//         sendButton.disabled = true;
//         userInput.disabled = true;
//         if (event.wasClean) {
//             console.log(`[close] Connection closed cleanly, code=${event.code} reason=${event.reason}`);
//              appendMessage("Connection to agent closed.", 'agent', false);
//         } else {
//             console.error('[close] Connection died');
//              appendMessage("Connection to agent lost. Attempting to reconnect...", 'agent', false);
//              setTimeout(connectWebSocket, 5000);
//         }
//     };
// }

// // Optional: Add an initial loading/connecting message
// // Use false for typing effect on this initial message


// // Automatically connect when the page loads
// connectWebSocket();




// function scrollToBottom() {
//     chatBox.scrollTop = chatBox.scrollHeight;
// }

// async function sendMessage() {
//     const message = userInput.value.trim();
//     if (message && websocket && websocket.readyState === WebSocket.OPEN) {
//         // Display user message instantly without typing effect
//         appendMessage(message, 'user', false);
//         //scrollToBottom();

//         // Send message to backend via WebSocket
//         await websocket.send(message);

//         // Clear input field
//         userInput.value = '';

//         // Optionally disable input while agent is processing
//         // sendButton.disabled = true;
//         // userInput.disabled = true;

//     } else if (websocket && websocket.readyState !== WebSocket.OPEN) {
//         console.warn("WebSocket is not connected.");
//          appendMessage("Cannot send message: Connection to agent is not open.", 'agent', false); // No typing for errors
//     } else if (!message) {
//         console.log("Input is empty, not sending.");
//     }
// }

// // --- Event Listeners ---
// sendButton.addEventListener('click', sendMessage);

// userInput.addEventListener('keypress', async function(event) {
//     if (event.key === 'Enter') {
//         event.preventDefault();
//         await sendMessage();
//     }
// });

// // Disable input initially until connected
// sendButton.disabled = true;
// userInput.disabled = true;


// static/script.js
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

// --- State for managing the current agent response ---
// Holds the div element for the current agent response being typed into.
// Used to update the thinking message or append subsequent chunks.
let currentAgentMessageElement = null;
let isTyping = false; // Flag to indicate if typing animation is currently in progress

// --- WebSocket Setup ---
const websocketUrl = `ws://${window.location.host}/ws`;
let websocket;

function connectWebSocket() {
    websocket = new WebSocket(websocketUrl);

    websocket.onopen = function(event) {
        console.log('WebSocket connection opened:', event);
        // Use createAndAppendMessage for static initial message
        createAndAppendMessage("Connected to the agent.", 'agent', { typingEffect: false });
        enableInput(); // Enable input after successful connection
    };

    websocket.onmessage = async function(event) {
        console.log('Message from server:', event.data);

        const messageData = event.data;

        // Assume the backend sends a specific signal for the end of the response
        if (messageData === "<<<END_OF_RESPONSE>>>") {
            console.log("End of response signal received.");
            // Ensure any pending typing finishes before enabling input
            while(isTyping) {
                // Wait briefly for typing to potentially finish the last character
                await new Promise(resolve => setTimeout(resolve, 50));
            }
            enableInput(); // Re-enable input after response ends
            currentAgentMessageElement = null; // Reset the current message element for the next request
            return; // Stop processing this signal message
        }

        // Find or create the message element to type into
        let targetElement = currentAgentMessageElement;

        // If no active element (should be created in sendMessage with spinner),
        // or if the current one still contains the spinner (meaning this is the first chunk of actual response)
        if (!targetElement || targetElement.querySelector('.spinner')) {
             // If targetElement exists and has spinner, clear its content (placeholder text + spinner)
             if(targetElement && targetElement.querySelector('.spinner')) {
                  targetElement.innerHTML = ''; // Clear placeholder text and spinner
             } else if (!targetElement) {
                 // Fallback: create a new element if somehow currentAgentMessageElement was null
                 // This shouldn't happen if sendMessage properly sets it up, but is a safeguard.
                 console.warn("Received message chunk but no active message element. Creating new (fallback).");
                 targetElement = createAndAppendMessage(null, 'agent', { typingEffect: true }); // Create a new element
             }
             // Now targetElement is the correct message div, and its content is cleared if it was the thinking message.
             // Set it as the current element if it wasn't already (e.g., in the fallback case)
             currentAgentMessageElement = targetElement;
        }

        // Now type the received data chunk into the target element
        // The typeMessageChunk function will handle the typing animation.
        await typeMessageChunk(currentAgentMessageElement, messageData);

        // Keep scrolling to the bottom as messages arrive and are typed
        scrollToBottom();
    };

    websocket.onerror = function(event) {
        console.error('WebSocket error observed:', event);
        // Find or create the message element to display the error
         let targetElement = currentAgentMessageElement;
         if (!targetElement) {
              // Create a new message element for the error if no active one exists
              targetElement = createAndAppendMessage(null, 'agent', { typingEffect: false });
         }

         // Update the element with an error message
         targetElement.innerHTML = ''; // Clear any placeholder/spinner/partial text
         targetElement.textContent = "Error during processing. Please check server logs.";
         targetElement.classList.add('agent-message'); // Ensure correct class

        enableInput(); // Re-enable input on error
        currentAgentMessageElement = null; // Reset the current message element state
        isTyping = false; // Stop any potential typing animation
    };

    websocket.onclose = function(event) {
        console.log('WebSocket connection closed:', event);
         // Find or create the message element to display the close status
         let targetElement = currentAgentMessageElement;
         if (!targetElement) {
              // Create a new message element for the close status if no active one exists
              targetElement = createAndAppendMessage(null, 'agent', { typingEffect: false });
         }

         // Update the element with the close status
         targetElement.innerHTML = ''; // Clear any placeholder/spinner/partial text
         if (event.wasClean) {
             targetElement.textContent = "Connection closed.";
         } else {
             targetElement.textContent = "Connection to agent lost.";
         }
         targetElement.classList.add('agent-message'); // Ensure correct class


        enableInput(); // Re-enable input on close
        currentAgentMessageElement = null; // Reset the current message element state
        isTyping = false; // Stop any potential typing animation

        // Removed automatic reconnect logic in the previous modification
    };
}

// Automatically connect when the page loads
connectWebSocket();


// --- Chat UI Functions ---

// Function to create and append a new message element
// sender: 'user' or 'agent'
// text: Initial text content (optional)
// options: { placeholder: string, spinner: boolean, typingEffect: boolean }
function createAndAppendMessage(text, sender, options = {}) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', sender + '-message');

    // Add base text or placeholder
    if (text) {
        messageElement.textContent = text;
    } else if (options.placeholder) {
         messageElement.textContent = options.placeholder;
    }

    // Add spinner if requested
    if (options.spinner) {
         const spinnerSpan = document.createElement('span');
         spinnerSpan.classList.add('spinner');
         // If there's text, add space before spinner. If not, spinner is the main content.
         if(text || options.placeholder) {
             // Add a small space before the spinner if there's text
             messageElement.appendChild(document.createTextNode(' '));
         }
         messageElement.appendChild(spinnerSpan);
    }

    // Note: Typing effect itself is handled by typeMessageChunk, which appends to an existing element.
    // This flag in options can be used to indicate intent, but doesn't start typing here.

    chatBox.appendChild(messageElement);
    scrollToBottom();
    return messageElement; // Return the created element
}

// Function to type text into an existing message element chunk by chunk
async function typeMessageChunk(element, textChunk) {
    isTyping = true; // Set typing flag

    // Append the text chunk character by character
    for (let i = 0; i < textChunk.length; i++) {
        // Append character
        element.textContent += textChunk.charAt(i);
        // Add a small delay
        await new Promise(resolve => setTimeout(resolve, 15)); // Adjust typing speed (milliseconds per character)
        // Use a small delay before scrolling to allow DOM updates
        if (i % 10 === 0) { // Scroll every few characters to reduce overhead
             scrollToBottom();
        }
    }

    isTyping = false; // Clear typing flag after chunk is typed
}


// Optimized scrollToBottom with a small delay
function scrollToBottom() {
    // Use a slight delay to ensure DOM updates are rendered before scrolling
    setTimeout(() => {
        chatBox.scrollTop = chatBox.scrollHeight;
    }, 0);
}

// Disable input and button
function disableInput() {
    userInput.disabled = true;
    sendButton.disabled = true;
    sendButton.textContent = 'Wait...'; // Indicate waiting state
    sendButton.classList.add('opacity-50', 'cursor-not-allowed'); // Add Tailwind disabled styles
}

// Enable input and button
function enableInput() {
    userInput.disabled = false;
    sendButton.disabled = false;
    sendButton.textContent = 'Send'; // Reset button text
    sendButton.classList.remove('opacity-50', 'cursor-not-allowed'); // Remove Tailwind disabled styles
    userInput.focus(); // Return focus to input
}


// --- Event Listeners ---
sendButton.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', async function(event) {
    if (event.key === 'Enter') {
        event.preventDefault(); // Prevent default form submission
        await sendMessage();
    }
});

// --- Initial Setup ---
// Disable input initially until connected
disableInput(); // Disable initially

// Optional: Add an initial loading/connecting message when the page loads
createAndAppendMessage("Connecting to the agent...", 'agent', { typingEffect: true });