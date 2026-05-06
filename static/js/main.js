// Utility functions
function showLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = '<div class="loading-spinner"></div><p>Loading...</p>';
    }
}

function hideLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container && container.querySelector('.loading-spinner')) {
        container.innerHTML = '';
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <div class="error-content">
            <span>⚠️</span>
            <p>${message}</p>
            <button onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    document.body.insertBefore(errorDiv, document.body.firstChild);
    
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// Session management
function checkSession() {
    fetch('/api/check-session')
        .then(response => response.json())
        .then(data => {
            if (!data.authenticated && window.location.pathname !== '/login' && window.location.pathname !== '/') {
                window.location.href = '/login';
            }
        })
        .catch(() => {});
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Add smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
    
    // Auto-check session on protected pages
    if (window.location.pathname !== '/' && window.location.pathname !== '/login') {
        checkSession();
    }
});