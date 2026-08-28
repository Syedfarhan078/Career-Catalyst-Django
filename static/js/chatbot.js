/* ============================================================
   CHATBOT.JS — Client-Side Career Assistant Router
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
    const launcher = document.getElementById('chatbot-launcher');
    const windowEl = document.getElementById('chatbot-window');
    const closeBtn = document.getElementById('chatbot-close');
    const chatForm = document.getElementById('chatbot-form');
    const chatInput = document.getElementById('chatbot-input');
    const msgContainer = document.getElementById('chatbot-messages');

    if (!launcher || !windowEl || !msgContainer) return;

    // Retrieve URLs dynamically from template data-attributes
    const urls = {
        career: windowEl.dataset.urlCareer || '#',
        resume: windowEl.dataset.urlResume || '#',
        ats: windowEl.dataset.urlAts || '#',
        community: windowEl.dataset.urlCommunity || '#',
        interview: windowEl.dataset.urlInterview || '#'
    };

    // Toggle Chat visibility
    launcher.addEventListener('click', () => {
        windowEl.classList.toggle('open');
        if (windowEl.classList.contains('open')) {
            chatInput.focus();
            scrollChatToBottom();
        }
    });

    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            windowEl.classList.remove('open');
        });
    }

    // Load conversation history from sessionStorage
    const loadConversation = () => {
        const history = sessionStorage.getItem('cc_chat_history');
        if (history) {
            msgContainer.innerHTML = history;
        } else {
            // Initial Welcome Message
            appendMessage('bot', `Hello! I am your Career Catalyst assistant. How can I help you today? You can ask me about:<br>
            • 🧭 <strong>Career Guidance & Roadmaps</strong><br>
            • 📄 <strong>Resumes & ATS Analysis</strong><br>
            • 👥 <strong>Mentorship Booking</strong><br>
            • 📝 <strong>Interview Practice</strong>`);
        }
        scrollChatToBottom();
    };

    const saveConversation = () => {
        sessionStorage.setItem('cc_chat_history', msgContainer.innerHTML);
    };

    const appendMessage = (sender, text) => {
        const bubble = document.createElement('div');
        bubble.className = `chat-msg ${sender}`;
        bubble.innerHTML = text;
        msgContainer.appendChild(bubble);
        scrollChatToBottom();
        saveConversation();
    };

    const scrollChatToBottom = () => {
        msgContainer.scrollTop = msgContainer.scrollHeight;
    };

    // Process user input
    if (chatForm) {
        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const text = chatInput.value.trim();
            if (!text) return;

            // Append user text
            appendMessage('user', escapeHTML(text));
            chatInput.value = '';

            // Generate bot reply after a small visual typing delay
            setTimeout(() => {
                const reply = generateBotReply(text.toLowerCase());
                appendMessage('bot', reply);
            }, 600);
        });
    }

    const escapeHTML = (str) => {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    };

    // Client-Side Keyword Routing Logic
    const generateBotReply = (query) => {
        // Career, paths, guidance, roadmaps
        if (matchKeywords(query, ['career', 'path', 'guidance', 'roadmap', 'recommendation', 'recommend', 'goal'])) {
            return `To explore career paths, assess your skill gaps, and get dynamic 30/90-day action plans, try our <strong>AI Career Guidance</strong> dashboard:<br>
            <a href="${urls.career}" class="chatbot-link">Explore Career Guidance <i class="bi bi-arrow-right-short"></i></a>`;
        }
        
        // Resume, CV, ATS score
        if (matchKeywords(query, ['resume', 'cv', 'ats', 'builder', 'analyzer', 'portfolio', 'score'])) {
            return `You can compile ATS-optimized resumes and grade them against job descriptions using our tools:<br>
            • <a href="${urls.resume}" class="chatbot-link">Open Resume Builder <i class="bi bi-arrow-right-short"></i></a><br>
            • <a href="${urls.ats}" class="chatbot-link">ATS Resume Analyzer <i class="bi bi-arrow-right-short"></i></a>`;
        }

        // Mentor, book, marketplace
        if (matchKeywords(query, ['mentor', 'marketplace', 'booking', 'chat', 'marketplace', 'consultation'])) {
            return `To book 1-on-1 sessions with industry experts, schedule guidance meetings, and chat with approved developers, check out the marketplace:<br>
            <a href="${urls.community}" class="chatbot-link">Book a Mentor <i class="bi bi-arrow-right-short"></i></a>`;
        }

        // Interview, coding, mcq, proctor
        if (matchKeywords(query, ['interview', 'prep', 'mcq', 'coding challenge', 'mock', 'proctor', 'practice', 'aptitude'])) {
            return `Practice proctored MCQs, behavioral rounds, and solve Python coding challenges inside our practice sandbox:<br>
            <a href="${urls.interview}" class="chatbot-link">Practice Interviews <i class="bi bi-arrow-right-short"></i></a>`;
        }

        // Greetings
        if (matchKeywords(query, ['hi', 'hello', 'hey', 'start', 'welcome', 'help'])) {
            return `Hello! How can I support your career preparation today? Feel free to ask about:<br>
            • 🧭 <strong>Career Guidance & Roadmaps</strong><br>
            • 📄 <strong>Resumes & ATS Analysis</strong><br>
            • 👥 <strong>Mentorship Booking</strong><br>
            • 📝 <strong>Interview Practice</strong>`;
        }

        // Fallback default
        return `I'm not sure I understand that query. Could you please specify if you are looking for assistance with:<br>
        • 🧭 <strong>Career Guidance & Roadmaps</strong><br>
        • 📄 <strong>Resumes & ATS Analysis</strong><br>
        • 👥 <strong>Mentorship Booking</strong><br>
        • 📝 <strong>Interview Practice</strong>`;
    };

    const matchKeywords = (query, keywords) => {
        return keywords.some(k => query.includes(k));
    };

    // Initialize Conversation
    loadConversation();
});
