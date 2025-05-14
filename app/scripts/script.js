// static/script.js
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

let currentAgentMessageElement = null;
let isTyping = false;
const typingQueue = [];

const websocketUrl = `ws://localhost:8000/ws`; // 或者根据你的实际地址调整
let websocket;
let re_ask = false; // 标记当前是否处于等待用户对追问进行回复的状态

// 用于存储从 uml_diagram_bytes_start 消息中获取的图片元数据
let pendingImageContext = null; 

function connectWebSocket() {
    console.log(`尝试连接到 ${websocketUrl}`);
    websocket = new WebSocket(websocketUrl);

    websocket.onopen = function(event) {
        console.log('WebSocket 连接已打开:', event);
        createAndAppendMessage("已连接到智能助理。", 'agent', { typingEffect: false });
        enableInput();
    };

    websocket.onmessage = async function(event) {
        console.log('服务器消息:', event.data);

        // 1. 首先处理二进制数据 (对应方案A: 原始字节流)
        if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
            console.log("收到二进制数据 (应为图片)");
            
            const imageBlob = (event.data instanceof Blob) ? event.data : new Blob([event.data], { type: 'image/png' }); // 假设是PNG
            const imageUrl = URL.createObjectURL(imageBlob);

            // 为图片创建一个新的消息容器
            const imageContainer = createAndAppendMessage(null, 'agent', {}); // sender是 'agent'
            imageContainer.innerHTML = ''; // 清空 createAndAppendMessage 可能添加的占位符

            const imgElement = document.createElement('img');
            imgElement.src = imageUrl;
            imgElement.alt = pendingImageContext ? pendingImageContext.filename : "UML Diagram"; // 使用之前信号中的文件名
            imgElement.style.maxWidth = "90%"; // 限制图片最大宽度
            imgElement.style.maxHeight = "1000px"; // 限制图片最大高度
            imgElement.style.display = "block";   // 让图片独占一行
            imgElement.style.marginTop = "10px";
            imgElement.style.marginBottom = "10px";
            imgElement.style.border = "1px solid #ccc"; // 可选：给图片加个边框
            imgElement.style.borderRadius = "4px";   // 可选：圆角

            imageContainer.appendChild(imgElement);
            scrollToBottom();

            pendingImageContext = null; // 清除等待的图片上下文

            // 可选: 图片加载后释放 Object URL 以节省内存，但需小心处理
            // imgElement.onload = () => { URL.revokeObjectURL(imageUrl); };
            return; // 二进制数据已处理
        }

        // 2. 处理字符串数据 (文本消息, JSON信号等)
        if (typeof event.data === 'string') {
            let messageTextForTyping = event.data; // 默认将收到的字符串用于打字效果
            let isSignalMessage = false;     // 标记是否为特殊信号消息，这类消息不进入打字队列

            try {
                const parsedJson = JSON.parse(event.data);
                // 如果能解析为JSON，则检查是否为我们定义的图片信号
                if (parsedJson && typeof parsedJson === 'object') {
                    if (parsedJson.type === 'uml_diagram_bytes_start') {
                        console.log(`后端信号: 开始发送UML图片字节流: ${parsedJson.filename}`);
                        pendingImageContext = parsedJson; // 存储图片元数据，等待后续的二进制数据
                        isSignalMessage = true; // 这是一个信号，不直接显示
                    } else if (parsedJson.type === 'uml_diagram_data_uri') {
                        // 处理方案B (Base64 Data URI)
                        console.log(`后端发送Base64编码的UML图片: ${parsedJson.filename}`);
                        const imageContainer = createAndAppendMessage(null, 'agent', {});
                        imageContainer.innerHTML = ''; 

                        const imgElement = document.createElement('img');
                        imgElement.src = parsedJson.data_uri;
                        imgElement.alt = parsedJson.filename || "UML Diagram (Data URI)";
                        imgElement.style.maxWidth = "90%";
                        imgElement.style.maxHeight = "600px";
                        imgElement.style.display = "block";
                        imgElement.style.marginTop = "10px";
                        imgElement.style.marginBottom = "10px";
                        imgElement.style.border = "1px solid #ccc";
                        imgElement.style.borderRadius = "4px";

                        imageContainer.appendChild(imgElement);
                        scrollToBottom();
                        isSignalMessage = true; // Data URI 图片已处理，不进入打字队列
                    } else {
                        // 其他类型的JSON消息，如果想让它显示出来，可以转为字符串
                        // messageTextForTyping = JSON.stringify(parsedJson, null, 2); // 美化JSON输出
                        // 或者，如果Agent的文本回复本身就是JSON，你可能需要提取其中的特定字段
                        // 默认情况下，如果不是特定信号，我们就让它作为文本进入打字队列
                        // (如果你的Agent会发送JSON作为常规回复，你可能需要在这里细化处理)
                        // 为了安全，如果JSON结构不符合预期，还是以字符串形式打出
                        messageTextForTyping = event.data;
                    }
                }
            } catch (e) {
                // 解析JSON失败，说明是普通文本消息，messageTextForTyping已经是event.data
            }

            // 处理后端发送的特殊信号字符串
            if (messageTextForTyping === "<<<END_OF_RESPONSE>>>") {
                console.log("收到响应结束信号。");
                if (isTyping && typingQueue.length > 0 && currentAgentMessageElement) {
                    currentAgentMessageElement.textContent += typingQueue.join('');
                    typingQueue.length = 0;
                }
                while(isTyping) { await new Promise(resolve => setTimeout(resolve, 20)); }
                enableInput();
                currentAgentMessageElement = null;
                re_ask = false; // 完整响应结束，重置追问状态
                isSignalMessage = true;
            } else if (messageTextForTyping === '<<<END_OF_RESPONSE_OF_REASK>>>') {
                console.log("收到追问响应结束信号。");
                re_ask = true; // 设置追问状态，下一个用户输入将带上追问前缀
                if (isTyping && typingQueue.length > 0 && currentAgentMessageElement) {
                    currentAgentMessageElement.textContent += typingQueue.join('');
                    typingQueue.length = 0;
                }
                while(isTyping) { await new Promise(resolve => setTimeout(resolve, 20)); }
                enableInput(); // 允许用户输入对追问的回复
                currentAgentMessageElement = null;
                isSignalMessage = true;
            } else if (messageTextForTyping === "<<<NEEDS_REASK_RESPONSE>>>") { // 来自ReAsk工具的信号
                console.log("Agent发信号表示需要追问回复。UI应体现这一点。");
                // 这个信号本身不显示为文本。实际的追问问题文本应该在此信号之前已发送。
                // re_ask 标志通常由 <<<END_OF_RESPONSE_OF_REASK>>> 设置。
                // 这个信号可以用于更精细地控制UI进入追问输入模式。
                isSignalMessage = true;
            }


            if (isSignalMessage) {
                return; // 特殊信号已处理，不进入打字队列
            }

            // --- 打字效果逻辑 ---
            let targetElement = currentAgentMessageElement;
            if (!targetElement || targetElement.querySelector('.spinner')) {
                if (targetElement && targetElement.querySelector('.spinner')) {
                    targetElement.innerHTML = ''; // 清除"Thinking..."和spinner
                } else if (!targetElement) {
                    // Fallback: 如果没有当前消息元素，创建一个 (理论上不应发生)
                    targetElement = createAndAppendMessage(null, 'agent', {});
                }
                currentAgentMessageElement = targetElement;
            }
            
            // 将收到的文本块（确保末尾有换行符，如果它代表一个完整的消息段）添加到打字队列
            typingQueue.push(messageTextForTyping.endsWith("\n") ? messageTextForTyping : messageTextForTyping + "\n");

            if (!isTyping) {
                await processTypingQueue();
            }
            scrollToBottom();
        }
    };

    websocket.onerror = function(event) {
        console.error('WebSocket 错误:', event);
        let targetElement = currentAgentMessageElement;
        if (!targetElement) {
            targetElement = createAndAppendMessage(null, 'agent', { typingEffect: false });
        }
        targetElement.innerHTML = '';
        targetElement.textContent = "处理过程中发生错误。请检查服务器日志。";
        targetElement.classList.add('error-message'); // 可以添加特定错误样式
        typingQueue.length = 0;
        isTyping = false;
        enableInput();
        currentAgentMessageElement = null;
    };

    websocket.onclose = function(event) {
        console.log('WebSocket 连接已关闭:', event);
        let targetElement = currentAgentMessageElement;
        // 即使没有 currentAgentMessageElement，也创建一个新的来显示关闭信息
        if (!targetElement && chatBox) { // 确保 chatBox 存在
             targetElement = createAndAppendMessage(null, 'agent', { typingEffect: false });
        }
        
        if (targetElement) { // 只有在元素存在时才更新它
            targetElement.innerHTML = '';
            if (event.wasClean) {
                targetElement.textContent = "连接已关闭。";
            } else {
                targetElement.textContent = "与智能助理的连接已丢失。请刷新页面重试。";
            }
            targetElement.classList.add('system-message'); // 可以添加特定系统消息样式
        } else if (chatBox) { // 如果 targetElement 仍未创建，直接在 chatBox 底部追加
            const p = document.createElement('p');
            p.classList.add('message', 'system-message');
            p.textContent = event.wasClean ? "连接已关闭。" : "与智能助理的连接已丢失。请刷新页面重试。";
            chatBox.appendChild(p);
        }

        typingQueue.length = 0;
        isTyping = false;
        // 不在这里调用 enableInput，因为连接已关闭，输入应保持禁用直到重新连接
        // disableInput(); // 确保禁用
        userInput.disabled = true; // 明确禁用
        sendButton.disabled = true;
        sendButton.textContent = '已断开';
        sendButton.classList.add('opacity-50', 'cursor-not-allowed');
        currentAgentMessageElement = null;
    };
}

connectWebSocket();

function createAndAppendMessage(text, sender, options = {}) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', sender + '-message');

    if (text) {
        messageElement.textContent = text;
    } else if (options.placeholder) {
        messageElement.textContent = options.placeholder;
    }

    if (options.spinner) {
        const spinnerSpan = document.createElement('span');
        spinnerSpan.classList.add('spinner');
        if (text || options.placeholder) {
            messageElement.appendChild(document.createTextNode(' '));
        }
        messageElement.appendChild(spinnerSpan);
    }

    chatBox.appendChild(messageElement);
    scrollToBottom(); // 每次添加消息后都滚动
    return messageElement;
}

async function processTypingQueue() {
    if (isTyping || typingQueue.length === 0 || !currentAgentMessageElement) {
        return;
    }
    isTyping = true;
    while (typingQueue.length > 0) {
        const textChunk = typingQueue.shift();
        for (let i = 0; i < textChunk.length; i++) {
            currentAgentMessageElement.textContent += textChunk.charAt(i);
            await new Promise(resolve => setTimeout(resolve, 15)); // 打字速度
            if ((currentAgentMessageElement.textContent.length % 20) === 0) {
                scrollToBottom();
            }
        }
        scrollToBottom();
    }
    isTyping = false;
}

function scrollToBottom() {
    setTimeout(() => {
        chatBox.scrollTop = chatBox.scrollHeight;
    }, 0);
}

function disableInput() {
    userInput.disabled = true;
    sendButton.disabled = true;
    sendButton.textContent = '等待...';
    sendButton.classList.add('opacity-50', 'cursor-not-allowed');
}

function enableInput() {
    userInput.disabled = false;
    sendButton.disabled = false;
    sendButton.textContent = '发送';
    sendButton.classList.remove('opacity-50', 'cursor-not-allowed');
    userInput.focus();
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return; // 如果消息为空，则不发送
    
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        createAndAppendMessage(message, 'user');
        disableInput();
        currentAgentMessageElement = createAndAppendMessage("正在思考中...", 'agent', { spinner: true });
        
        let messageToSend = message;
        if (re_ask === true) {
            console.log("发送追问回复 (带前缀)");
            messageToSend = `<<<REASK>>>${message}`;
            re_ask = false; // 发送追问回复后，重置追问状态
        }
        await websocket.send(messageToSend);
        userInput.value = '';
    } else {
        console.log("WebSocket 未连接或消息为空。");
        createAndAppendMessage("发送失败，连接未建立或已断开。", 'agent', { typingEffect: false });
    }
}

sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', async function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        await sendMessage();
    }
});

disableInput(); // 初始禁用输入，直到连接成功
createAndAppendMessage("正在连接到UML AGENT...", 'agent', { typingEffect: false });