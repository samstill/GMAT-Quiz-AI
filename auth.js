document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = '/api'; // Use relative URL to match other files
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const showRegisterLink = document.getElementById('show-register');
    const showLoginLink = document.getElementById('show-login');
    const notificationContainer = document.getElementById('notification-container');

    // Theme toggle functionality
    const themeToggleBtn = document.getElementById('theme-toggle');
    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');

    // Load saved theme
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
        sunIcon.classList.remove('hidden');
        moonIcon.classList.add('hidden');
    } else {
        sunIcon.classList.add('hidden');
        moonIcon.classList.remove('hidden');
    }

    themeToggleBtn.addEventListener('click', () => {
        document.body.classList.toggle('light-mode');
        const isLight = document.body.classList.contains('light-mode');
        
        localStorage.setItem('theme', isLight ? 'light' : 'dark');
        
        if (isLight) {
            sunIcon.classList.remove('hidden');
            moonIcon.classList.add('hidden');
        } else {
            sunIcon.classList.add('hidden');
            moonIcon.classList.remove('hidden');
        }
    });

    // Toggle between login and register forms
    showRegisterLink.addEventListener('click', () => {
        loginForm.classList.add('hidden');
        registerForm.classList.remove('hidden');
    });

    showLoginLink.addEventListener('click', () => {
        registerForm.classList.add('hidden');
        loginForm.classList.remove('hidden');
    });

    // Handle registration
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('register-username').value;
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;
        const geminiKey = document.getElementById('register-gemini-key').value;

        try {
            const response = await fetch(`${API_BASE_URL}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password })
            });

            if (response.ok) {
                // Store Gemini API key if provided (for use after login)
                if (geminiKey) {
                    localStorage.setItem('pendingGeminiApiKey', geminiKey);
                }
                
                showNotification('Registration successful! Please login.', 'success');
                registerForm.reset();
                showLoginLink.click();
            } else {
                const error = await response.json();
                showNotification(`Registration failed: ${error.detail}`, 'error');
            }
        } catch (error) {
            showNotification('An error occurred during registration.', 'error');
        }
    });

    // Handle login
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        const geminiKey = document.getElementById('gemini-key').value;

        try {
            const loginResponse = await fetch(`${API_BASE_URL}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (!loginResponse.ok) {
                const error = await loginResponse.json();
                throw new Error(error.detail || 'Login failed');
            }

            const loginData = await loginResponse.json();
            
            // Store the API key and user information
            localStorage.setItem('apiKey', loginData.api_key);
            localStorage.setItem('username', loginData.username);
            localStorage.setItem('userId', loginData.user_id);
            
            // Store Gemini API key if provided
            if (geminiKey) {
                localStorage.setItem('geminiApiKey', geminiKey);
            } else {
                // Check if there's a pending Gemini API key from registration
                const pendingKey = localStorage.getItem('pendingGeminiApiKey');
                if (pendingKey) {
                    localStorage.setItem('geminiApiKey', pendingKey);
                    localStorage.removeItem('pendingGeminiApiKey');
                }
            }

            showNotification('Login successful! Redirecting...', 'success');
            setTimeout(() => {
                window.location.href = 'index.html';
            }, 1000);

        } catch (error) {
            showNotification(`Login failed: ${error.message}`, 'error');
        }
    });

    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `p-4 rounded-md shadow-lg text-white ${type === 'success' ? 'bg-green-500' : 'bg-red-500'}`;
        notification.textContent = message;
        notificationContainer.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
});
