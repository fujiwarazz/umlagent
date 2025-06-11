const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const planDisplay = document.getElementById('planDisplay'); // 新增：获取计划显示区域

let currentAgentMessageElement = null;
let isTyping = false;
let typingQueue = [];

const websocketUrl = `http://127.0.0.1:8000/ws`;
let websocket;
let re_ask = false;
let pendingImageContext = null;

// 用于存储当前计划的数据
let currentPlan = null;

function connectWebSocket() {
    console.log(`尝试连接到 ${websocketUrl}`);
    websocket = new WebSocket(websocketUrl);

    websocket.onopen = function(event) {
        console.log('WebSocket 连接已打开:', event);
        createAndAppendMessage("已连接到 UML Agent 智能助理。", 'agent');
        enableInput();
        renderPlan(); // 初始渲染空的计划面板
    };

    websocket.onmessage = async function(event) {
        console.log('服务器消息:', event.data);

        if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
            console.log("收到二进制数据 (应为图片)");
            const imageBlob = (event.data instanceof Blob) ? event.data : new Blob([event.data], { type: 'image/png' });
            const imageUrl = URL.createObjectURL(imageBlob);
            const imageContainer = createAndAppendMessage(null, 'agent', {});
            imageContainer.innerHTML = '';
            
            // 创建一个包裹图片的容器，并添加放大效果的提示
            const imageWrapper = document.createElement('div');
            imageWrapper.className = 'uml-diagram-wrapper';
            imageWrapper.style.position = 'relative';
            imageWrapper.style.cursor = 'zoom-in';
            
            // 创建图片元素
            const imgElement = document.createElement('img');
            imgElement.src = imageUrl;
            imgElement.alt = pendingImageContext ? pendingImageContext.filename : "UML Diagram";
            imgElement.className = 'uml-diagram';
            imgElement.style.maxWidth = "90%";
            imgElement.style.maxHeight = "600px"; // 调整了图片最大高度
            imgElement.style.display = "block";
            imgElement.style.marginTop = "10px";
            imgElement.style.marginBottom = "10px";
            imgElement.style.border = "3px solid #33ff66"; // 像素风边框
            imgElement.style.borderRadius = "0"; // 方形边框
            imgElement.style.boxShadow = "4px 4px 0 #121224"; // 像素风阴影

            // 添加点击提示标签
            const zoomHint = document.createElement('div');
            zoomHint.className = 'zoom-hint';
            zoomHint.innerHTML = '🔍 点击放大';
            zoomHint.style.position = 'absolute';
            zoomHint.style.bottom = '15px';
            zoomHint.style.right = '15px';
            zoomHint.style.background = 'rgba(18, 18, 36, 0.7)';
            zoomHint.style.color = '#33ff66';
            zoomHint.style.padding = '5px 10px';
            zoomHint.style.fontFamily = 'VT323, monospace';
            zoomHint.style.fontSize = '1.1em';
            zoomHint.style.border = '2px solid #33ff66';
            
            // 点击图片时放大显示
            imgElement.addEventListener('click', function() {
                createFullscreenImageView(imageUrl, pendingImageContext ? pendingImageContext.filename : "UML Diagram");
            });
            
            // 将图片和提示添加到容器
            imageWrapper.appendChild(imgElement);
            imageWrapper.appendChild(zoomHint);
            imageContainer.appendChild(imageWrapper);
            
            scrollToBottom();
            pendingImageContext = null;
            return;
        }

        if (typeof event.data === 'string') {
            let messageTextForTyping = event.data;
            let isSignalMessage = false;
            let potentialPlanData = null;

            // 检查是否为计划创建或更新的特定消息格式
            if (messageTextForTyping.startsWith("<<<PLAN_CREATED>>>")) {
                console.log("收到 PLAN_CREATED 信号");
                isSignalMessage = true;
                const planContent = messageTextForTyping.substring("<<<PLAN_CREATED>>>".length).trim();
                // 将计划内容也显示在聊天框中，因为它可能包含工具的观测结果
                messageTextForTyping = planContent; 
                potentialPlanData = parsePlanFromString(planContent);
                if (potentialPlanData) {
                    currentPlan = potentialPlanData;
                    renderPlan();
                }
                 // 不设置 isSignalMessage = true，让它作为普通消息打印出来，因为它包含了观测结果
            } else if (messageTextForTyping.startsWith("<<<MARK_PLAN>>>")) {
                console.log("收到 MARK_PLAN 信号");
                isSignalMessage = true; // 这是一个纯粹的更新信号，不应在聊天框中打印信号本身
                const updateContent = messageTextForTyping.substring("<<<MARK_PLAN>>>".length).trim();
                const [indexStr, newStatus] = updateContent.split(',');
                const index = parseInt(indexStr, 10);
                if (currentPlan && currentPlan.steps[index] && newStatus) {
                    currentPlan.steps[index].status = newStatus.trim();
                    // 更新进度
                    const completedSteps = currentPlan.steps.filter(s => s.status === 'completed').length;
                    currentPlan.progress = (completedSteps / currentPlan.steps.length) * 100;
                    // 更新状态总结文本
                    const statusCounts = countPlanStepStatus(currentPlan.steps);
                    currentPlan.statusSummary = `${statusCounts.completed} completed, ${statusCounts.in_progress} in progress, ${statusCounts.blocked} blocked, ${statusCounts.not_started} not started`;

                    renderPlan(); // 重新渲染计划面板以反映状态变化
                } else {
                    console.warn("无法更新计划步骤: 索引无效或状态缺失", index, newStatus, currentPlan);
                }
            }


            try {
                const parsedJson = JSON.parse(event.data);
                if (parsedJson && typeof parsedJson === 'object') {
                    if (parsedJson.type === 'uml_diagram_bytes_start') {
                        console.log(`后端信号: 开始发送UML图片字节流: ${parsedJson.filename}`);
                        pendingImageContext = parsedJson;
                        isSignalMessage = true;
                    } else if (parsedJson.type === 'uml_diagram_data_uri') {
                        console.log(`后端发送Base64编码的UML图片: ${parsedJson.filename}`);
                        const imageContainer = createAndAppendMessage(null, 'agent', {});
                        imageContainer.innerHTML = ''; 
                        const imgElement = document.createElement('img');
                        imgElement.src = parsedJson.data_uri;
                        imgElement.alt = parsedJson.filename || "UML Diagram (Data URI)";
                        imgElement.style.maxWidth = "90%";
                        imgElement.style.maxHeight = "600px"; // 调整了图片最大高度
                        imgElement.style.display = "block";
                        imgElement.style.marginTop = "10px";
                        imgElement.style.marginBottom = "10px";
                        imgElement.style.border = "1px solid #ccc";
                        imgElement.style.borderRadius = "4px";
                        imageContainer.appendChild(imgElement);
                        scrollToBottom();
                        isSignalMessage = true;
                    } else if (!isSignalMessage) { // 如果不是已处理的 plan 信号或图片信号
                        messageTextForTyping = event.data; // 保持原始数据给打字效果
                    }
                }
            } catch (e) {
                // 解析JSON失败，messageTextForTyping 已经是 event.data
            }

            // 仅当不是 MARK_PLAN 信号时才处理其他信号 (因为 MARK_PLAN 已经设置 isSignalMessage=true)
            if (!messageTextForTyping.startsWith("<<<MARK_PLAN>>>")) {
                if (messageTextForTyping === "<<<END_OF_RESPONSE>>>") {
                    console.log("收到响应结束信号。");
                    if (isTyping && typingQueue.length > 0 && currentAgentMessageElement) {
                        currentAgentMessageElement.textContent += typingQueue.join('');
                        typingQueue.length = 0;
                    }
                    while(isTyping) { await new Promise(resolve => setTimeout(resolve, 20)); }
                    enableInput();
                    currentAgentMessageElement = null;
                    re_ask = false;
                    isSignalMessage = true;
                } else if (messageTextForTyping === '<<<END_OF_RESPONSE_OF_REASK>>>') {
                    console.log("收到追问响应结束信号。");
                    re_ask = true;
                    if (isTyping && typingQueue.length > 0 && currentAgentMessageElement) {
                        currentAgentMessageElement.textContent += typingQueue.join('');
                        typingQueue.length = 0;
                    }
                    while(isTyping) { await new Promise(resolve => setTimeout(resolve, 20)); }
                    enableInput();
                    currentAgentMessageElement = null;
                    isSignalMessage = true;
                } else if (messageTextForTyping === "<<<NEEDS_REASK_RESPONSE>>>") {
                    console.log("Agent发信号表示需要追问回复。UI应体现这一点。");
                    isSignalMessage = true;
                }
            }


            if (isSignalMessage && !messageTextForTyping.startsWith("<<<PLAN_CREATED>>>")) {
                // 如果是信号消息 (除了PLAN_CREATED，因为它也包含要打印的文本)
                return; 
            }
            
            // --- 打字效果逻辑 ---
            // (打字逻辑保持不变, 但 messageTextForTyping 可能已经是处理过的 planContent)
            let targetElement = currentAgentMessageElement;
            if (!targetElement || targetElement.querySelector('.spinner')) {
                if (targetElement && targetElement.querySelector('.spinner')) {
                    targetElement.innerHTML = '';
                } else if (!targetElement) {
                    targetElement = createAndAppendMessage(null, 'agent', {});
                }
                currentAgentMessageElement = targetElement;
            }
            typingQueue.push(messageTextForTyping.endsWith("\n") ? messageTextForTyping : messageTextForTyping + "\n");
            if (!isTyping) {
                await processTypingQueue();
            }
            scrollToBottom();
        }
    };

    // ... (onerror, onclose 逻辑保持不变) ...
    websocket.onerror = function(event) {
        console.error('WebSocket 错误:', event);
        handleConnectionIssue("处理过程中发生错误。请检查服务器日志。", true);
    };

    websocket.onclose = function(event) {
        console.log('WebSocket 连接已关闭:', event);
        const message = event.wasClean ? "连接已关闭。" : "与智能助理的连接已丢失。请刷新页面重试。";
        handleConnectionIssue(message, false); // isError = false
    };
}

function handleConnectionIssue(message, isError) {
    let targetElement = currentAgentMessageElement;
    if (!targetElement && chatBox) {
         targetElement = createAndAppendMessage(null, 'agent', { placeholder: message });
         if(isError) targetElement.classList.add('error-message');
         else targetElement.classList.add('system-message');
    } else if (targetElement) {
        targetElement.innerHTML = '';
        targetElement.textContent = message;
        if(isError) targetElement.classList.add('error-message');
        else targetElement.classList.add('system-message');
    } else if (chatBox) {
        const p = document.createElement('p');
        p.classList.add('message', isError ? 'error-message' : 'system-message');
        p.textContent = message;
        chatBox.appendChild(p);
    }

    typingQueue.length = 0;
    isTyping = false;
    userInput.disabled = true;
    sendButton.disabled = true;
    sendButton.textContent = '已断开';
    sendButton.classList.add('opacity-50', 'cursor-not-allowed');
    currentAgentMessageElement = null;
    currentPlan = null; // 连接断开，清空计划
    renderPlan(); // 渲染空计划
}


function parsePlanFromString(rawString) {
    // 尝试移除工具观测结果前缀，直到找到 "Plan:"
    let planContent = rawString;
    const planStartIndex = rawString.indexOf("Plan:");
    if (planStartIndex !== -1) {
        planContent = rawString.substring(planStartIndex);
    } else {
        console.warn("在原始字符串中未找到 'Plan:' 起始标志。", rawString);
        // 即使没有 "Plan:"，也尝试继续解析，因为后续的 regex 可能还能匹配到 Steps 等
    }

    const plan = {
        title: "任务计划", // 默认标题
        id: null,
        progress: 0,
        statusSummary: "无信息",
        steps: []
    };

    // 提取 Plan 标题和 ID
    // 更新正则表达式以确保从行首开始匹配 Plan:
    const titleMatch = planContent.match(/^Plan:\s*(.*?)(?:\s*\(ID:\s*([a-zA-Z0-9_]+)\))?$/m);
    if (titleMatch) {
        plan.title = titleMatch[1].trim();
        if (titleMatch[2]) { // ID 是可选的
            plan.id = titleMatch[2].trim();
        }
    } else {
        console.warn("未能从以下内容解析出Plan标题和ID:", planContent.split('\n')[0]);
    }
    // (保持你现有的 progressMatch 和 statusSummaryMatch 不变，因为它们看起来是独立的)
    const progressMatch = planContent.match(/Progress:\s*(\d+)\/(\d+)\s*steps completed\s*\((\d+\.?\d*)%\)/m);
    if (progressMatch) {
        plan.progress = parseFloat(progressMatch[3]);
    }

    const statusSummaryMatch = planContent.match(/Status:\s*(.*)/m);
    if (statusSummaryMatch) {
        plan.statusSummary = statusSummaryMatch[1].trim();
    }

    // 提取 Steps (这里的逻辑可能需要特别注意多行匹配和步骤的准确分割)
    // 你原来的 regex: /(\d+)\.\s*\[\s*([x\s])\s*\]\s*(.*)/gim
    // 这个 regex 看起来还行，但要确保它能正确处理所有步骤格式
    const stepsSectionMatch = planContent.match(/Steps:\s*([\s\S]*)/im);
    if (stepsSectionMatch) {
        const stepsBlock = stepsSectionMatch[1];
        const stepsRegex = /^\s*(\d+)\.\s*\[\s*([x\s\*-]?)\s*\]\s*(.*)/gm; // 修改以匹配行首，并允许多种状态指示符
        let match;
        while ((match = stepsRegex.exec(stepsBlock)) !== null) {
            const statusChar = match[2].trim().toLowerCase();
            let status = 'not_started';
            if (statusChar === 'x') {
                status = 'completed';
            } else if (statusChar === '*') { // 假设 * 代表进行中 (你可以自定义)
                status = 'in_progress';
            } else if (statusChar === '-') { // 假设 - 代表阻塞 (你可以自定义)
                status = 'blocked';
            }

            plan.steps.push({
                id: match[1], // 步骤的数字索引
                text: match[3].trim(),
                status: status
            });
        }
    } else {
        console.warn("未能从计划内容中找到 'Steps:' 部分。");
    }

    // 重新计算初始进度和状态（如果需要且未从字符串中解析到）
    if (plan.steps.length > 0) {
        const completedSteps = plan.steps.filter(s => s.status === 'completed').length;
        plan.progress = (completedSteps / plan.steps.length) * 100; // 总是基于当前状态计算

        const statusCounts = countPlanStepStatus(plan.steps);
        plan.statusSummary = `${statusCounts.completed} completed, ${statusCounts.in_progress} in progress, ${statusCounts.blocked} blocked, ${statusCounts.not_started} not started`;
    } else {
        // 如果没有解析到任何步骤，并且标题ID也没有，则认为解析失败，返回null
        if (!plan.id && plan.title === "任务计划") { // 检查是否真的什么都没解析到
             console.warn("解析出的计划步骤为空且无有效标题/ID。", planString);
             return null;
        }
    }

    console.log("解析后的计划对象:", JSON.parse(JSON.stringify(plan))); // 打印解析结果以供调试
    return plan;
}
function countPlanStepStatus(steps) {
    const counts = { completed: 0, in_progress: 0, blocked: 0, not_started: 0 };
    steps.forEach(step => {
        counts[step.status] = (counts[step.status] || 0) + 1;
    });
    return counts;
}


// --- 渲染计划面板的函数 ---
function renderPlan() {
    if (!planDisplay) return;

    if (!currentPlan || !currentPlan.steps || currentPlan.steps.length === 0) {
        planDisplay.innerHTML = '<p style="color: #66aaff; font-size: 1.1em; text-align: center;">暂无计划，或计划正在生成中...</p>';
        return;
    }

    let html = `
        <h3 style="font-family: 'Press Start 2P', cursive; font-size: 1rem; margin-bottom: 12px; color: #33ff66; text-shadow: 2px 2px 0 #121224;">${currentPlan.title || '任务计划'}</h3>
        ${currentPlan.id ? `<span class="plan-title-id">ID: ${currentPlan.id}</span>` : ''}
        <div class="plan-progress-bar-container">
            <div class="plan-progress-bar" style="width: ${currentPlan.progress || 0}%;"></div>
        </div>
        <p class="plan-status-summary">${currentPlan.progress.toFixed(1)}% 完成. ${currentPlan.statusSummary || ''}</p>
        <ul class="plan-steps-list">
    `;

    currentPlan.steps.forEach(step => {
        let statusIcon = '□';
        if (step.status === 'completed') statusIcon = '■';
        else if (step.status === 'in_progress') statusIcon = '▶';
        else if (step.status === 'blocked') statusIcon = '×';
        
        html += `
            <li class="plan-step ${step.status}" data-step-id="${step.id}">
                <span class="plan-step-icon"></span>
                <span class="plan-step-text">${step.text}</span>
            </li>
        `;
    });

    html += `</ul>`;
    planDisplay.innerHTML = html;
}


// ... (createAndAppendMessage, processTypingQueue, scrollToBottom, disableInput, enableInput, sendMessage 函数保持不变) ...
function createAndAppendMessage(text, sender, options = {}) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', sender + '-message');

    if (text) {
        // 将 Markdown 的反引号代码块转换为 <pre><code>
        // 并处理行内反引号代码
        let processedText = text.replace(/```([\s\S]*?)```/g, (match, codeContent) => {
            // 对于代码块，移除可能的语言标识符（如果不需要特别处理）
            const langMatch = codeContent.match(/^[a-zA-Z]+\n/);
            let actualCode = codeContent;
            if(langMatch){
                actualCode = codeContent.substring(langMatch[0].length);
            }
            return `<pre><code>${actualCode.trim()}</code></pre>`;
        });
        processedText = processedText.replace(/`([^`]+)`/g, '<code>$1</code>');
        messageElement.innerHTML = processedText; // 使用 innerHTML 来渲染 pre 和 code 标签
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
    scrollToBottom(); 
    return messageElement;
}

async function processTypingQueue() {
    if (isTyping || typingQueue.length === 0 || !currentAgentMessageElement) {
        return;
    }
    isTyping = true;
    while (typingQueue.length > 0) {
        const textChunk = typingQueue.shift();
        // 打字效果不应该尝试解析 HTML，所以我们直接追加文本内容
        // 如果 textChunk 包含 HTML (例如来自 PLAN_CREATED 的 pre/code)，则直接设置 innerHTML
        if (textChunk.includes('<pre>') || textChunk.includes('<code>')) {
             // 为了打字效果，我们还是逐字添加，但这意味着HTML标签也会被逐字打印
             // 一个更好的方式是，如果检测到是富文本，就一次性添加到innerHTML
             // 但这会破坏打字效果。
             // 折中：对于包含HTML的，不使用逐字打字，直接追加。
             // 但当前设计 currentAgentMessageElement.textContent 破坏了这一点。
             // 为了简单起见，这里仍用 textContent，这意味着 HTML 标签会以文本形式打出。
             // 如果要支持富文本打字，processTypingQueue 需要更复杂。
             // 或者，createAndAppendMessage 在收到包含代码块的文本时，直接设置innerHTML，不走打字队列。
             // 我们需要确保打字效果能正确处理或绕过HTML。

            // 简单处理：如果包含HTML，则直接附加，不逐字打印 (牺牲打字效果，保证HTML渲染)
            if (currentAgentMessageElement.innerHTML === '' && (textChunk.includes('<pre>') || textChunk.includes('<code>'))) {
                 currentAgentMessageElement.innerHTML += textChunk; // 直接附加整个HTML块
            } else { // 否则，逐字打印 (主要针对纯文本部分)
                for (let i = 0; i < textChunk.length; i++) {
                    currentAgentMessageElement.textContent += textChunk.charAt(i);
                    await new Promise(resolve => setTimeout(resolve, 10)); // 稍快一点的打字速度
                    if ((currentAgentMessageElement.textContent.length % 30) === 0) { //减少滚动频率
                        scrollToBottom();
                    }
                }
            }
        } else { //纯文本，逐字打印
            for (let i = 0; i < textChunk.length; i++) {
                currentAgentMessageElement.textContent += textChunk.charAt(i);
                await new Promise(resolve => setTimeout(resolve, 10));
                if ((currentAgentMessageElement.textContent.length % 30) === 0) {
                    scrollToBottom();
                }
            }
        }
        scrollToBottom();
    }
    isTyping = false;
}

function scrollToBottom() {
    setTimeout(() => {
        if(chatBox) chatBox.scrollTop = chatBox.scrollHeight;
    }, 0);
}

function disableInput() {
    if(userInput) userInput.disabled = true;
    if(sendButton) {
        sendButton.disabled = true;
        sendButton.textContent = '等待...';
        sendButton.classList.add('opacity-50', 'cursor-not-allowed');
    }
}

function enableInput() {
    if(userInput) {
        userInput.disabled = false;
        userInput.focus();
    }
    if(sendButton) {
        sendButton.disabled = false;
        sendButton.textContent = '发送';
        sendButton.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return; 
    
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        createAndAppendMessage(message, 'user'); // user message doesn't need complex typing
        disableInput();
        currentAgentMessageElement = createAndAppendMessage(null, 'agent', { placeholder: "智能助理思考中...", spinner: true });
        
        let messageToSend = message;
        if (re_ask === true) {
            console.log("发送追问回复 (带前缀)");
            messageToSend = `<<<REASK>>>${message}`;
            re_ask = false; 
        }
        websocket.send(messageToSend); // await 不是必需的，send 是非阻塞的
        userInput.value = '';
    } else {
        console.log("WebSocket 未连接或消息为空。");
        createAndAppendMessage("发送失败，连接未建立或已断开。", 'agent');
    }
}


sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', async function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        await sendMessage();
    }
});

// 初始状态
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        disableInput(); 
        createAndAppendMessage("正在连接到 UML Agent...", 'agent');
        connectWebSocket();
    });
} else {
    // DOMContentLoaded has already fired
    disableInput();
    createAndAppendMessage("正在连接到 UML Agent...", 'agent');
    connectWebSocket();
}

// 创建全屏图片查看功能
function createFullscreenImageView(imageUrl, altText) {
    // 创建模态框背景 - 使用固定定位覆盖整个视口
    const modal = document.createElement('div');
    modal.className = 'pixel-modal';
    modal.style.position = 'fixed';
    modal.style.top = '0';
    modal.style.left = '0';
    modal.style.width = '100vw'; // 使用视口宽度单位
    modal.style.height = '100vh'; // 使用视口高度单位
    modal.style.backgroundColor = 'rgba(10, 10, 20, 0.95)'; // 增加背景不透明度
    modal.style.display = 'flex';
    modal.style.justifyContent = 'center';
    modal.style.alignItems = 'center';
    modal.style.zIndex = '10000';
    modal.style.padding = '0'; // 移除内边距以实现真正的全屏
    modal.style.margin = '0'; // 移除外边距
    modal.style.boxSizing = 'border-box';
    modal.style.backdropFilter = 'blur(5px)';
    
    // 创建图片容器 - 占据几乎整个屏幕
    const imageContainer = document.createElement('div');
    imageContainer.className = 'pixel-modal-content';
    imageContainer.style.position = 'relative';
    imageContainer.style.width = '98vw'; // 几乎占据整个视口宽度
    imageContainer.style.height = '96vh'; // 几乎占据整个视口高度
    imageContainer.style.maxWidth = 'none'; // 移除最大宽度限制
    imageContainer.style.maxHeight = 'none'; // 移除最大高度限制
    imageContainer.style.border = '6px solid #33ff66';
    imageContainer.style.boxShadow = '0 0 0 3px #121224, 0 0 20px rgba(51, 255, 102, 0.6)';
    imageContainer.style.backgroundColor = '#1a1a2e';
    imageContainer.style.padding = '10px';
    imageContainer.style.overflow = 'hidden';
    imageContainer.style.display = 'flex';
    imageContainer.style.flexDirection = 'column';
    
    // 创建标题栏
    const titleBar = document.createElement('div');
    titleBar.style.display = 'flex';
    titleBar.style.justifyContent = 'space-between';
    titleBar.style.alignItems = 'center';
    titleBar.style.borderBottom = '3px dashed #33ff66';
    titleBar.style.marginBottom = '10px';
    titleBar.style.padding = '10px 0';
    
    // 创建关闭按钮
    const closeButton = document.createElement('button');
    closeButton.className = 'pixel-close-button';
    closeButton.innerHTML = '×';
    closeButton.style.width = '50px';
    closeButton.style.height = '50px';
    closeButton.style.backgroundColor = '#33ff66';
    closeButton.style.border = '3px solid #121224';
    closeButton.style.borderRadius = '0';
    closeButton.style.color = '#121224';
    closeButton.style.fontSize = '36px';
    closeButton.style.fontWeight = 'bold';
    closeButton.style.cursor = 'pointer';
    closeButton.style.display = 'flex';
    closeButton.style.justifyContent = 'center';
    closeButton.style.alignItems = 'center';
    closeButton.style.padding = '0';
    closeButton.style.lineHeight = '1';
    closeButton.style.marginLeft = '10px';
    
    // 创建图片标题
    const imageTitle = document.createElement('div');
    imageTitle.className = 'pixel-image-title';
    imageTitle.style.fontFamily = 'Press Start 2P, cursive';
    imageTitle.style.color = '#33ff66';
    imageTitle.style.fontSize = '1.2em';
    imageTitle.style.textAlign = 'center';
    imageTitle.style.flex = '1';
    imageTitle.textContent = altText || 'UML 图表';
    
    // 创建缩放信息显示
    const zoomDisplay = document.createElement('div');
    zoomDisplay.className = 'pixel-zoom-display';
    zoomDisplay.style.backgroundColor = 'rgba(18, 18, 36, 0.8)';
    zoomDisplay.style.color = '#33ff66';
    zoomDisplay.style.padding = '5px 15px';
    zoomDisplay.style.fontFamily = 'VT323, monospace';
    zoomDisplay.style.fontSize = '1.4em';
    zoomDisplay.style.border = '2px solid #33ff66';
    zoomDisplay.style.marginRight = '10px';
    zoomDisplay.style.minWidth = '120px';
    zoomDisplay.style.textAlign = 'center';
    
    // 图片包装器 - 使用flex-grow占据容器的所有可用空间
    const imageWrapper = document.createElement('div');
    imageWrapper.className = 'pixel-image-wrapper';
    imageWrapper.style.flex = '1';
    imageWrapper.style.display = 'flex';
    imageWrapper.style.justifyContent = 'center';
    imageWrapper.style.alignItems = 'center';
    imageWrapper.style.position = 'relative';
    imageWrapper.style.overflow = 'hidden';
    imageWrapper.style.width = '100%';
    imageWrapper.style.height = 'calc(100% - 70px)'; // 减去标题栏和底栏的高度
    
    // 创建放大后的图片 - 初始不设置尺寸限制，由缩放控制
    const fullImage = document.createElement('img');
    fullImage.src = imageUrl;
    fullImage.alt = altText;
    fullImage.className = 'pixel-fullscreen-image';
    fullImage.style.maxHeight = '100%';
    fullImage.style.maxWidth = '100%';
    fullImage.style.transformOrigin = 'center center';
    fullImage.style.objectFit = 'contain'; // 确保图片完整显示
    fullImage.style.cursor = 'grab';
    fullImage.style.transition = 'transform 0.1s';
    
    // 底部控制栏
    const controlsBar = document.createElement('div');
    controlsBar.style.display = 'flex';
    controlsBar.style.justifyContent = 'space-between';
    controlsBar.style.alignItems = 'center';
    controlsBar.style.borderTop = '3px dashed #33ff66';
    controlsBar.style.marginTop = '10px';
    controlsBar.style.padding = '10px 0';
    
    // 帮助提示
    const helpText = document.createElement('div');
    helpText.className = 'pixel-help-text';
    helpText.style.color = '#33ff66';
    helpText.style.fontFamily = 'VT323, monospace';
    helpText.style.fontSize = '1.4em';
    helpText.innerHTML = '🔍 滚轮缩放 | 拖动移动 | 双击重置 | ESC关闭';
    
    // 按钮组
    const buttonGroup = document.createElement('div');
    buttonGroup.style.display = 'flex';
    buttonGroup.style.gap = '10px';
    
    // 缩小按钮
    const zoomOutBtn = document.createElement('button');
    zoomOutBtn.className = 'pixel-control-btn';
    zoomOutBtn.innerHTML = '➖';
    zoomOutBtn.title = '缩小 (-)';
    
    // 重置按钮
    const resetBtn = document.createElement('button');
    resetBtn.className = 'pixel-control-btn';
    resetBtn.innerHTML = '↺';
    resetBtn.title = '重置缩放 (0)';
    
    // 放大按钮
    const zoomInBtn = document.createElement('button');
    zoomInBtn.className = 'pixel-control-btn';
    zoomInBtn.innerHTML = '➕';
    zoomInBtn.title = '放大 (+)';
    
    // 初始化缩放和平移变量
    let scale = 1;
    let isDragging = false;
    let startX, startY, translateX = 0, translateY = 0;
    
    // 显示当前缩放级别
    function updateZoomDisplay() {
        zoomDisplay.textContent = `缩放: ${Math.round(scale * 100)}%`;
    }
    
    // 应用变换到图片
    function applyTransform() {
        fullImage.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
    }
    
    // 重置缩放和位置
    function resetView() {
        scale = 1;
        translateX = 0;
        translateY = 0;
        applyTransform();
        updateZoomDisplay();
    }
    
    // 鼠标滚轮缩放
    imageWrapper.addEventListener('wheel', function(e) {
        e.preventDefault();
        const rect = imageWrapper.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        // 计算缩放因子 - 增大步长使缩放更快
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.max(0.1, Math.min(10, scale * delta));
        
        // 计算新的平移值，以使鼠标位置保持不变
        if (scale !== newScale) {
            const scaleRatio = newScale / scale;
            translateX = mouseX - scaleRatio * (mouseX - translateX);
            translateY = mouseY - scaleRatio * (mouseY - translateY);
            scale = newScale;
        }
        
        applyTransform();
        updateZoomDisplay();
    });
    
    // 鼠标拖动操作
    fullImage.addEventListener('mousedown', function(e) {
        if (e.button === 0) { // 只在左键点击时触发
            e.preventDefault();
            isDragging = true;
            startX = e.clientX - translateX;
            startY = e.clientY - translateY;
            fullImage.style.cursor = 'grabbing';
        }
    });
    
    document.addEventListener('mousemove', function(e) {
        if (isDragging) {
            translateX = e.clientX - startX;
            translateY = e.clientY - startY;
            applyTransform();
        }
    });
    
    document.addEventListener('mouseup', function() {
        if (isDragging) {
            isDragging = false;
            fullImage.style.cursor = 'grab';
        }
    });
    
    // 双击重置图片
    fullImage.addEventListener('dblclick', resetView);
    
    // 按钮点击事件
    zoomInBtn.addEventListener('click', function() {
        scale = Math.min(10, scale * 1.2);
        applyTransform();
        updateZoomDisplay();
    });
    
    zoomOutBtn.addEventListener('click', function() {
        scale = Math.max(0.1, scale * 0.8);
        applyTransform();
        updateZoomDisplay();
    });
    
    resetBtn.addEventListener('click', resetView);
    
    // 添加键盘控制
    const keyboardControls = function(e) {
        // ESC 关闭
        if (e.key === 'Escape') {
            document.body.removeChild(modal);
            document.removeEventListener('keydown', keyboardControls);
        }
        // + 键放大
        else if (e.key === '+' || e.key === '=') {
            e.preventDefault();
            scale = Math.min(10, scale * 1.2);
            applyTransform();
            updateZoomDisplay();
        }
        // - 键缩小
        else if (e.key === '-') {
            e.preventDefault();
            scale = Math.max(0.1, scale * 0.8);
            applyTransform();
            updateZoomDisplay();
        }
        // 0 键重置
        else if (e.key === '0') {
            e.preventDefault();
            resetView();
        }
        // 方向键移动
        else if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
            e.preventDefault();
            const moveAmount = 50;
            if (e.key === 'ArrowUp') translateY += moveAmount;
            if (e.key === 'ArrowDown') translateY -= moveAmount;
            if (e.key === 'ArrowLeft') translateX += moveAmount;
            if (e.key === 'ArrowRight') translateX -= moveAmount;
            applyTransform();
        }
    };
    
    // 添加点击关闭模态框的处理
    closeButton.addEventListener('click', function() {
        document.body.removeChild(modal);
        document.removeEventListener('keydown', keyboardControls);
    });
    
    // 点击模态框背景也可以关闭
    modal.addEventListener('click', function(event) {
        if (event.target === modal) {
            document.body.removeChild(modal);
            document.removeEventListener('keydown', keyboardControls);
        }
    });
    
    // 阻止图片区域的点击事件冒泡到模态框
    imageContainer.addEventListener('click', function(e) {
        e.stopPropagation();
    });
    
    // 按钮组装
    buttonGroup.appendChild(zoomOutBtn);
    buttonGroup.appendChild(resetBtn);
    buttonGroup.appendChild(zoomInBtn);
    
    // 标题栏装配
    titleBar.appendChild(imageTitle);
    titleBar.appendChild(zoomDisplay);
    titleBar.appendChild(closeButton);
    
    // 控制栏装配
    controlsBar.appendChild(helpText);
    controlsBar.appendChild(buttonGroup);
    
    // 图片包装器装配
    imageWrapper.appendChild(fullImage);
    
    // 组装模态框
    imageContainer.appendChild(titleBar);
    imageContainer.appendChild(imageWrapper);
    imageContainer.appendChild(controlsBar);
    modal.appendChild(imageContainer);
    
    // 添加到页面
    document.body.appendChild(modal);
    
    // 添加键盘事件监听器
    document.addEventListener('keydown', keyboardControls);
    
    // 初始显示缩放级别
    updateZoomDisplay();
    
    // 将图片调整为最佳初始显示大小
    setTimeout(() => {
        resetView();
        
        // 检测图片是否太大或太小，调整到适合的大小
        fullImage.onload = function() {
            const imgAspect = this.naturalWidth / this.naturalHeight;
            const containerAspect = imageWrapper.clientWidth / imageWrapper.clientHeight;
            
            // 如果图片太大，自动缩小以适应容器
            if (this.naturalWidth > imageWrapper.clientWidth * 0.9 || 
                this.naturalHeight > imageWrapper.clientHeight * 0.9) {
                resetView(); // 确保初始显示合适
            }
        };
    }, 100);
}