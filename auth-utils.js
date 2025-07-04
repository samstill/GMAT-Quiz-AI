// Authentication utilities for GMAT Quiz App
class AuthManager {
    constructor() {
        this.API_BASE_URL = '/api'; // Use relative URL to match the index.html pattern
    }

    // Check if user is authenticated
    isAuthenticated() {
        const apiKey = localStorage.getItem('apiKey');
        const username = localStorage.getItem('username');
        return !!(apiKey && username);
    }

    // Get the user's API key
    getApiKey() {
        return localStorage.getItem('apiKey');
    }

    // Get the user's username
    getUsername() {
        return localStorage.getItem('username');
    }

    // Get the user's Gemini API key
    getGeminiApiKey() {
        return localStorage.getItem('geminiApiKey');
    }

    // Get user ID
    getUserId() {
        return localStorage.getItem('userId');
    }

    // Logout user
    logout() {
        localStorage.removeItem('apiKey');
        localStorage.removeItem('username');
        localStorage.removeItem('userId');
        localStorage.removeItem('geminiApiKey');
        window.location.href = 'auth.html';
    }

    // Redirect to login if not authenticated
    requireAuth() {
        if (!this.isAuthenticated()) {
            window.location.href = 'auth.html';
            return false;
        }
        return true;
    }

    // Make authenticated API request
    async makeAuthenticatedRequest(url, options = {}) {
        const apiKey = this.getApiKey();
        if (!apiKey) {
            throw new Error('No API key available');
        }

        const defaultOptions = {
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json',
                ...options.headers
            }
        };

        const finalOptions = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(url, finalOptions);
            
            // If unauthorized, redirect to login
            if (response.status === 401) {
                this.logout();
                return;
            }
            
            return response;
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    // Show notification
    showNotification(message, type = 'info', duration = 3000) {
        // Create notification container if it doesn't exist
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.className = 'fixed top-5 right-5 z-50 space-y-2';
            document.body.appendChild(container);
        }

        const notification = document.createElement('div');
        notification.className = `p-4 rounded-md shadow-lg text-white transform translate-x-full transition-transform duration-300 ${
            type === 'success' ? 'bg-green-500' : 
            type === 'error' ? 'bg-red-500' : 
            type === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'
        }`;
        notification.textContent = message;
        
        container.appendChild(notification);
        
        // Slide in
        setTimeout(() => {
            notification.classList.remove('translate-x-full');
        }, 100);

        // Slide out and remove
        setTimeout(() => {
            notification.classList.add('translate-x-full');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, duration);
    }

    // Initialize user info display (if needed)
    initUserDisplay() {
        const username = this.getUsername();
        if (username) {
            // Update any user display elements
            const userElements = document.querySelectorAll('[data-user-display]');
            userElements.forEach(element => {
                element.textContent = username;
            });
        }
    }

    // Add logout button if needed
    addLogoutButton(container) {
        const logoutBtn = document.createElement('button');
        logoutBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16,17 21,12 16,7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            Logout
        `;
        logoutBtn.className = 'icon-button flex items-center gap-2 px-4 py-2 text-sm';
        logoutBtn.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            z-index: 100;
            background: var(--card-bg-color);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-color);
            transition: all 0.3s ease;
        `;
        logoutBtn.addEventListener('click', () => this.logout());
        
        if (container) {
            container.appendChild(logoutBtn);
        } else {
            document.body.appendChild(logoutBtn);
        }
        
        return logoutBtn;
    }
}

// Create global instance
window.authManager = new AuthManager();

// Auto-check authentication on page load
document.addEventListener('DOMContentLoaded', () => {
    // Only require auth if not on auth page
    if (!window.location.pathname.includes('auth.html')) {
        window.authManager.requireAuth();
        window.authManager.initUserDisplay();
    }
});
