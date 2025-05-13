// script.js
const chatHistory = document.getElementById('chat-history');
const queryForm = document.getElementById('query-form');
const userInput = document.getElementById('user-input');

// 处理表单提交
queryForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    
    if (!query) return;

    // 显示用户消息
    addMessageToChat(query, 'user');
    userInput.value = '';

    try {
        // 发送请求并建立SSE连接
        const response = await fetch('/api/start-conversation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || 'Failed to start conversation');
        }

        const conversationId = data.conversationId;
        
        // 创建SSE连接
        const eventSource = new EventSource(`/api/stream?conversationId=${conversationId}`);
        
        // 处理消息事件
        eventSource.addEventListener('message', (event) => {
            try {
                const chunk = JSON.parse(event.data);
                if (chunk.type === 'llm_thought') {
                    addMessageToChat(chunk.content, 'agent', true);
                } else if (chunk.type === 'tool_call') {
                    addMessageToChat(`🛠️ 工具调用: ${chunk.content}`, 'agent', true);
                } else if (chunk.type === 'tool_result') {
                    addMessageToChat(`🎯 工具结果: ${chunk.content}`, 'agent', true);
                } else if (chunk.type === 'final_response') {
                    addMessageToChat(chunk.content, 'agent');
                    eventSource.close();
                } else if (chunk.type === 'error') {
                    addMessageToChat(`❌ 错误: ${chunk.content}`, 'agent');
                    eventSource.close();
                }
            } catch (error) {
                console.error('Error processing event:', error);
            }
        });

        // 处理错误
        eventSource.onerror = () => {
            addMessageToChat('⚠️ 连接已关闭或发生错误', 'agent');
            eventSource.close();
        };
    } catch (error) {
        addMessageToChat(`❌ 请求失败: ${error.message}`, 'agent');
    }
});

/**
 * 将消息添加到聊天记录
 * @param {string} message 
 * @param {string} type 'user' or 'agent'
 * @param {boolean} isPartial 是否是部分结果（如思考过程）
 */
function addMessageToChat(message, type, isPartial = false) {
    const messageContainer = document.createElement('div');
    messageContainer.className = 'chat-message';
    
    const messageElement = document.createElement('div');
    messageElement.className = `${type}-message`;
    
    // 如果是部分结果，添加CSS类用于特殊样式
    if (isPartial) {
        messageElement.classList.add('partial-result');
        messageElement.innerHTML = `<span class="streaming-marker"></span>${formatMessage(message)}`;
    } else {
        messageElement.innerHTML = formatMessage(message);
    }
    
    messageContainer.appendChild(messageElement);
    chatHistory.appendChild(messageContainer);
    
    // 滚动到底部
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

/**
 * 格式化消息，将特殊标记转换为HTML
 * @param {string} message 
 * @returns {string} HTML格式的消息
 */
function formatMessage(message) {
    // 处理特殊字符和缩进
    let processed = message;
    
    // 转义HTML
    processed = escapeHtml(processed);
    
    // 替换特殊符号
    processed = processed.replace(/(\u250c|\u2514|\u251c)/g, ' ');
    
    // 高亮显示特定模式
    processed = processed.replace(/(✨ .*? 的想法为:)/g, '<strong>$1</strong>');
    processed = processed.replace(/(🛠️ .*? 选择了 \d+ 个工具)/g, '<strong>$1</strong>');
    processed = processed.replace(/(🧰 工具的参数是:)/g, '<strong>$1</strong>');
    processed = processed.replace(/(🎯 工具 '.*?' 完成了它的任务! 其执行结果为:)/g, '<strong>$1</strong>');
    processed = processed.replace(/(🏁 Special tool '.*?' has completed the task!)/g, '<strong>$1</strong>');
    processed = processed.replace(/(🚨 出错啦! .*? 在思考时出现了错误)/g, '<strong class="error">$1</strong>');
    
    // 添加换行符
    processed = processed.replace(/\n/g, '<br>');
    
    return processed;
}

/**
 * 转义HTML字符串
 * @param {string} text 
 * @returns {string} 转义后的HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}