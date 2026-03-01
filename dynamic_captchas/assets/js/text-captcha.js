/**
 * Dynamic CAPTCHA Server - Enhanced JavaScript
 * Provides smooth interactions and better user experience
 */

function getStaticPositionRatios() {
    const randomSource =
        typeof window !== 'undefined' && typeof window.__CAPTCHA_STATIC_RANDOM === 'function'
            ? window.__CAPTCHA_STATIC_RANDOM
            : Math.random;

    const nextValue = () => {
        let value = randomSource();
        if (!Number.isFinite(value) || value < 0) {
            value = Math.random();
        }
        return Math.min(0.9999, Math.max(0, value));
    };

    return {
        leftRatio: nextValue(),
        topRatio: nextValue(),
    };
}

class CaptchaManager {
    constructor() {
        this.challengeId = null;
        this.isSubmitting = false;
        this.initializeElements();
        this.bindEvents();
        this.setupAnimations();
    }

    initializeElements() {
        this.input = document.getElementById('captcha-input');
        this.submitBtn = document.getElementById('submit-btn');
        this.messageDiv = document.getElementById('message');
        this.image = document.querySelector('.captcha-image');
        this.container = document.querySelector('.captcha-container');
        this.randomPosition = getStaticPositionRatios();
        this.handleResize = null;
        this.positionContainerRandomly();
        
        // Detect CAPTCHA type
        this.captchaType = this.detectCaptchaType();
    }
    
    detectCaptchaType() {
        if (document.querySelector('.icon-captcha')) {
            return 'icon';
        } else if (document.querySelector('.compact-captcha')) {
            return 'compact';
        } else {
            return 'text';
        }
    }

    bindEvents() {
        // Only bind text-based CAPTCHA events
        if (this.captchaType === 'text' || this.captchaType === 'compact') {
            // Submit button click
            if (this.submitBtn) {
                this.submitBtn.addEventListener('click', () => this.handleSubmit());
            }
            
            // Enter key press
            if (this.input) {
                this.input.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter' && !this.isSubmitting) {
                        this.handleSubmit();
                    }
                });

                // Input focus effects
                this.input.addEventListener('focus', () => {
                    if (this.input.parentElement) {
                        this.input.parentElement.classList.add('focused');
                    }
                });

                this.input.addEventListener('blur', () => {
                    if (this.input.parentElement) {
                        this.input.parentElement.classList.remove('focused');
                    }
                });

                // Real-time input validation
                this.input.addEventListener('input', (e) => {
                    this.validateInput(e.target.value);
                });
            }
        }
        // For icon CAPTCHAs, the template handles its own events
    }

    setupAnimations() {
        // Add entrance animation
        this.container.style.opacity = '0';
        this.container.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            this.container.style.transition = 'all 0.6s ease';
            this.container.style.opacity = '1';
            this.container.style.transform = 'translateY(0)';
        }, 100);
    }
    
    positionContainerRandomly() {
        if (!this.container) {
            return;
        }

        const margin = 20;
        const applyPosition = () => {
            const rect = this.container.getBoundingClientRect();
            const width = rect.width;
            const height = rect.height;
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;

            const availableWidth = Math.max(0, viewportWidth - width - margin * 2);
            const availableHeight = Math.max(0, viewportHeight - height - margin * 2);

            const left = availableWidth <= 0
                ? Math.max(0, (viewportWidth - width) / 2)
                : margin + this.randomPosition.leftRatio * availableWidth;

            const top = availableHeight <= 0
                ? Math.max(0, (viewportHeight - height) / 2)
                : margin + this.randomPosition.topRatio * availableHeight;

            this.container.style.left = `${left}px`;
            this.container.style.top = `${top}px`;
        };

        requestAnimationFrame(() => {
            applyPosition();
            setTimeout(applyPosition, 250);
        });

        if (!this.handleResize) {
            this.handleResize = () => applyPosition();
            window.addEventListener('resize', this.handleResize);
        }
    }

    validateInput(value) {
        // Remove any non-alphanumeric characters
        const cleanValue = value.replace(/[^a-zA-Z0-9]/g, '');
        if (value !== cleanValue) {
            this.input.value = cleanValue;
        }
    }

    async handleSubmit() {
        if (this.isSubmitting) return;

        const submission = this.input.value.trim();
        
        if (!submission) {
            this.showMessage('Please enter the CAPTCHA text.', 'error');
            this.input.focus();
            return;
        }

        this.isSubmitting = true;
        this.setSubmitState(true);

        try {
            const response = await fetch('/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    challenge_id: this.challengeId,
                    submission: submission
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showMessage(data.message, 'success');
                this.input.disabled = true;
                this.submitBtn.disabled = true;
                this.container.classList.add('solved');
                
                // Add confetti effect
                this.createConfettiEffect();
            } else {
                this.showMessage(data.message, 'error');
                // this.input.value = '';  // Commented out to preserve user input for self-correction training
                this.input.focus();
                
                // Shake animation for error
                this.container.classList.add('shake');
                setTimeout(() => {
                    this.container.classList.remove('shake');
                }, 500);
            }
        } catch (error) {
            this.showMessage('An error occurred. Please try again.', 'error');
            console.error('CAPTCHA submission error:', error);
        } finally {
            this.isSubmitting = false;
            this.setSubmitState(false);
        }
    }

    setSubmitState(isSubmitting) {
        if (isSubmitting) {
            this.submitBtn.innerHTML = '<span class="captcha-loading"></span>Submitting...';
            this.submitBtn.disabled = true;
            this.input.disabled = true;
        } else {
            this.submitBtn.innerHTML = 'Submit';
            this.submitBtn.disabled = false;
            this.input.disabled = false;
        }
    }

    showMessage(text, type) {
        this.messageDiv.textContent = text;
        this.messageDiv.className = `captcha-message ${type}`;
        this.messageDiv.classList.add('show');

        // Auto-hide success messages after 3 seconds
        if (type === 'success') {
            setTimeout(() => {
                this.messageDiv.classList.remove('show');
            }, 3000);
        }
    }

    createConfettiEffect() {
        const colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4ecdc4'];
        const confettiCount = 50;

        for (let i = 0; i < confettiCount; i++) {
            setTimeout(() => {
                const confetti = document.createElement('div');
                confetti.style.position = 'fixed';
                confetti.style.width = '10px';
                confetti.style.height = '10px';
                confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
                confetti.style.left = Math.random() * window.innerWidth + 'px';
                confetti.style.top = '-10px';
                confetti.style.borderRadius = '50%';
                confetti.style.pointerEvents = 'none';
                confetti.style.zIndex = '9999';
                confetti.style.animation = 'confetti-fall 3s linear forwards';

                document.body.appendChild(confetti);

                setTimeout(() => {
                    confetti.remove();
                }, 3000);
            }, i * 20);
        }
    }

    // Public method to set challenge ID
    setChallengeId(id) {
        this.challengeId = id;
    }
}

// Add confetti animation CSS
const style = document.createElement('style');
style.textContent = `
    @keyframes confetti-fall {
        0% {
            transform: translateY(-100vh) rotate(0deg);
            opacity: 1;
        }
        100% {
            transform: translateY(100vh) rotate(720deg);
            opacity: 0;
        }
    }

    .shake {
        animation: shake 0.5s ease-in-out;
    }

    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-5px); }
        75% { transform: translateX(5px); }
    }

    .captcha-container.solved {
        animation: success-pulse 0.6s ease-in-out;
    }

    @keyframes success-pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }

    .captcha-input-group.focused .captcha-input {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
`;
document.head.appendChild(style);

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.captchaManager = new CaptchaManager();
    
    // Set challenge ID from hidden input
    const challengeIdInput = document.getElementById('challenge-id');
    if (challengeIdInput) {
        window.captchaManager.setChallengeId(challengeIdInput.value);
    }
    
    // Focus on input only for text-based CAPTCHAs
    if (window.captchaManager.captchaType === 'text' || window.captchaManager.captchaType === 'compact') {
        const input = document.getElementById('captcha-input');
        if (input) {
            setTimeout(() => input.focus(), 500);
        }
    }
});
