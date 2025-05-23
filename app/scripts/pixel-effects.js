// 像素风特效脚本

// 音效控制
let soundEnabled = false; // 默认关闭，避免打扰用户
const typingSound = document.getElementById('typingSound');
const messageSentSound = document.getElementById('messageSentSound');
const messageReceivedSound = document.getElementById('messageReceivedSound');

// 创建声音控制按钮
function createSoundToggle() {
    const soundToggle = document.createElement('button');
    soundToggle.classList.add('sound-toggle');
    soundToggle.innerHTML = '🔇';
    soundToggle.title = '启用音效';
    soundToggle.style.position = 'absolute';
    soundToggle.style.top = '10px';
    soundToggle.style.right = '10px';
    soundToggle.style.background = '#121224';
    soundToggle.style.border = '2px solid #33ff66';
    soundToggle.style.color = '#33ff66';
    soundToggle.style.width = '30px';
    soundToggle.style.height = '30px';
    soundToggle.style.borderRadius = '0';
    soundToggle.style.cursor = 'pointer';
    soundToggle.style.zIndex = '10';
    
    soundToggle.addEventListener('click', () => {
        soundEnabled = !soundEnabled;
        soundToggle.innerHTML = soundEnabled ? '🔊' : '🔇';
        soundToggle.title = soundEnabled ? '禁用音效' : '启用音效';
    });
    
    document.body.appendChild(soundToggle);
}

// 打字音效
function playTypingSound() {
    if (!soundEnabled) return;
    try {
        typingSound.currentTime = 0;
        typingSound.volume = 0.2;
        typingSound.play();
    } catch (e) {
        console.log('音效播放失败', e);
    }
}

// 发送消息音效
function playMessageSentSound() {
    if (!soundEnabled) return;
    try {
        messageSentSound.currentTime = 0;
        messageSentSound.volume = 0.4;
        messageSentSound.play();
    } catch (e) {
        console.log('音效播放失败', e);
    }
}

// 收到消息音效
function playMessageReceivedSound() {
    if (!soundEnabled) return;
    try {
        messageReceivedSound.currentTime = 0;
        messageReceivedSound.volume = 0.4;
        messageReceivedSound.play();
    } catch (e) {
        console.log('音效播放失败', e);
    }
}

// 像素效果：添加扫描线
function addScanlines() {
    const scanlines = document.createElement('div');
    scanlines.classList.add('scanlines');
    scanlines.style.position = 'fixed';
    scanlines.style.top = '0';
    scanlines.style.left = '0';
    scanlines.style.width = '100%';
    scanlines.style.height = '100%';
    scanlines.style.pointerEvents = 'none';
    scanlines.style.zIndex = '9999';
    scanlines.style.backgroundImage = 'linear-gradient(0deg, transparent 0%, rgba(32, 32, 32, 0.05) 50%, transparent 100%)';
    scanlines.style.backgroundSize = '100% 4px';
    scanlines.style.opacity = '0.3';
    document.body.appendChild(scanlines);
}

// 重写打字效果，添加音效和像素效果
async function enhancedProcessTypingQueue() {
    if (typeof processTypingQueue === 'function') {
        const originalProcessTypingQueue = processTypingQueue;
        
        window.processTypingQueue = async function() {
            if (isTyping || typingQueue.length === 0 || !currentAgentMessageElement) {
                return;
            }
            
            isTyping = true;
            while (typingQueue.length > 0) {
                const textChunk = typingQueue.shift();
                
                if (textChunk.includes('<pre>') || textChunk.includes('<code>')) {
                    if (currentAgentMessageElement.innerHTML === '' && 
                        (textChunk.includes('<pre>') || textChunk.includes('<code>'))) {
                        currentAgentMessageElement.innerHTML += textChunk;
                    } else {
                        for (let i = 0; i < textChunk.length; i++) {
                            currentAgentMessageElement.textContent += textChunk.charAt(i);
                            if (i % 3 === 0) playTypingSound();
                            await new Promise(resolve => setTimeout(resolve, 20));
                            if ((currentAgentMessageElement.textContent.length % 30) === 0) {
                                scrollToBottom();
                            }
                        }
                    }
                } else {
                    for (let i = 0; i < textChunk.length; i++) {
                        currentAgentMessageElement.textContent += textChunk.charAt(i);
                        if (i % 3 === 0) playTypingSound();
                        await new Promise(resolve => setTimeout(resolve, 20));
                        if ((currentAgentMessageElement.textContent.length % 30) === 0) {
                            scrollToBottom();
                        }
                    }
                }
                
                scrollToBottom();
            }
            
            isTyping = false;
            playMessageReceivedSound();
        };
    }
}

// 重写发送消息方法，添加音效
function enhanceSendMessage() {
    if (typeof sendMessage === 'function') {
        const originalSendMessage = sendMessage;
        
        window.sendMessage = async function() {
            const message = userInput.value.trim();
            if (!message) return;
            
            playMessageSentSound();
            
            // 执行原始函数
            return originalSendMessage.apply(this, arguments);
        };
    }
}

// 添加像素动画效果：闪烁、失真等
function addPixelAnimations() {
    // 添加CSS动画
    const style = document.createElement('style');
    style.textContent = `
        @keyframes glitch {
            0% { transform: translate(0) }
            20% { transform: translate(-2px, 2px) }
            40% { transform: translate(-2px, -2px) }
            60% { transform: translate(2px, 2px) }
            80% { transform: translate(2px, -2px) }
            100% { transform: translate(0) }
        }
        
        .chat-header .header-title:hover {
            animation: glitch 0.2s steps(1) infinite;
            text-shadow: 2px 2px 0 #ff0, -2px -2px 0 #0ff;
        }
        
        .main-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(
                to bottom,
                transparent 50%,
                rgba(32, 32, 32, 0.05) 50%
            );
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 1000;
        }
    `;
    document.head.appendChild(style);
}

// 增强UML图的交互功能
function enhanceUmlDiagrams() {
    // 定期检查是否有新的UML图被添加
    setInterval(function() {
        const umlImages = document.querySelectorAll('.uml-diagram');
        umlImages.forEach(img => {
            // 如果图片还没有被增强，添加增强效果
            if (!img.dataset.enhanced) {
                img.dataset.enhanced = 'true';
                
                // 添加鼠标悬停效果
                img.addEventListener('mouseenter', function() {
                    this.style.transition = 'transform 0.2s steps(5)';
                    this.style.transform = 'scale(1.02)';
                    this.style.boxShadow = '6px 6px 0 #121224, 0 0 15px rgba(51, 255, 102, 0.3)';
                });
                
                img.addEventListener('mouseleave', function() {
                    this.style.transform = 'scale(1)';
                    this.style.boxShadow = '4px 4px 0 #121224';
                });
            }
        });
    }, 1000);
}

// 添加拖动功能，使图片可以在弹出窗口中拖动
function makeElementDraggable(element, handle) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    
    if (handle) {
        // 如果指定了拖动手柄，则手柄是可拖动元素的
        handle.style.cursor = 'move';
        handle.onmousedown = dragMouseDown;
    } else {
        // 否则，整个元素可拖动
        element.style.cursor = 'move';
        element.onmousedown = dragMouseDown;
    }
    
    function dragMouseDown(e) {
        e = e || window.event;
        e.preventDefault();
        // 获取鼠标初始位置
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        // 鼠标移动时调用
        document.onmousemove = elementDrag;
    }
    
    function elementDrag(e) {
        e = e || window.event;
        e.preventDefault();
        // 计算新位置
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        // 设置元素的新位置
        element.style.top = (element.offsetTop - pos2) + "px";
        element.style.left = (element.offsetLeft - pos1) + "px";
    }
    
    function closeDragElement() {
        // 停止拖动时
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

// 在窗口加载完成后执行初始化
window.addEventListener('DOMContentLoaded', () => {
    console.log('初始化像素风特效...');
    createSoundToggle();
    addScanlines();
    enhancedProcessTypingQueue();
    enhanceSendMessage();
    addPixelAnimations();
    enhanceUmlDiagrams();
});

// 兼容性检查：如果在DOMContentLoaded之后加载此脚本
if (document.readyState === 'interactive' || document.readyState === 'complete') {
    console.log('页面已加载，直接初始化像素风特效...');
    createSoundToggle();
    addScanlines();
    enhancedProcessTypingQueue();
    enhanceSendMessage();
    addPixelAnimations();
    enhanceUmlDiagrams();
}