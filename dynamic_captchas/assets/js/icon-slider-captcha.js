/**
 * Icon Slider CAPTCHA JavaScript
 * Handles card navigation and submission for the icon slider challenge.
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

class IconSliderCaptcha {
    constructor() {
        this.cards = Array.from(document.querySelectorAll('.icon-card'));
        this.dots = Array.from(document.querySelectorAll('.card-dot'));
        this.navLeft = document.querySelector('.nav-left');
        this.navRight = document.querySelector('.nav-right');
        this.submitBtn = document.getElementById('submit-btn');
        this.messageDiv = document.getElementById('message');
        this.container = document.querySelector('.captcha-container');
        this.challengeId = (document.getElementById('challenge-id') && document.getElementById('challenge-id').value) || '';
        this.currentIndex = 0;
        this.isSubmitting = false;
        this.requiresSubmit = true;
        this.randomPosition = getStaticPositionRatios();
        this.viewportResizeHandler = null;

        if (this.container) {
            const attr = (this.container.dataset && this.container.dataset.requiresSubmit) || 'true';
            this.requiresSubmit = attr.toLowerCase() !== 'false';
        }

        this.initialize();
    }

    initialize() {
        this.updateActiveCard();
        this.bindEvents();
        this.positionContainerRandomly();
        this.updateSubmitState();
    }

    bindEvents() {
        if (this.navLeft) {
            this.navLeft.addEventListener('click', () => this.navigate(-1));
        }
        if (this.navRight) {
            this.navRight.addEventListener('click', () => this.navigate(1));
        }
        if (this.dots && this.dots.length > 0) {
            this.dots.forEach((dot) => {
                dot.addEventListener('click', () => {
                    const idx = parseInt(dot.dataset.index || '0', 10);
                    this.setIndex(idx);
                });
            });
        }
        if (this.submitBtn) {
            this.submitBtn.addEventListener('click', () => this.handleSubmit());
        }

        if (!this.viewportResizeHandler) {
            this.viewportResizeHandler = () => this.positionContainerRandomly();
            window.addEventListener('resize', this.viewportResizeHandler);
        }
    }

    navigate(delta) {
        if (!this.cards.length) {
            return;
        }
        const total = this.cards.length;
        const nextIndex = (this.currentIndex + delta + total) % total;
        this.setIndex(nextIndex);
    }

    setIndex(idx) {
        if (!Number.isFinite(idx) || idx < 0 || idx >= this.cards.length) {
            return;
        }
        this.currentIndex = idx;
        this.updateActiveCard();
        this.updateSubmitState();
        if (!this.requiresSubmit) {
            this.handleSubmit();
        }
    }

    updateActiveCard() {
        this.cards.forEach((card, index) => {
            const isActive = index === this.currentIndex;
            card.classList.toggle('active', isActive);
            card.setAttribute('aria-hidden', (!isActive).toString());
        });

        if (this.dots && this.dots.length) {
            this.dots.forEach((dot, index) => {
                dot.classList.toggle('active', index === this.currentIndex);
            });
        }

        const indexInput = document.getElementById('current-index');
        if (indexInput) {
            indexInput.value = String(this.currentIndex);
        }
    }

    updateSubmitState() {
        if (!this.submitBtn) {
            return;
        }

        const hasCard = this.cards.length > 0;
        this.submitBtn.disabled = !hasCard || this.isSubmitting;
        this.submitBtn.style.opacity = this.submitBtn.disabled ? '0.6' : '1';
        this.submitBtn.style.cursor = this.submitBtn.disabled ? 'not-allowed' : 'pointer';
    }

    async handleSubmit() {
        if (this.isSubmitting) {
            return;
        }

        const activeCard = this.cards[this.currentIndex];
        if (!activeCard) {
            this.showMessage('No card selected. Slide through the cards first.', 'error');
            return;
        }

        if (!this.challengeId) {
            this.showMessage('Unable to submit right now. Please reload the CAPTCHA.', 'error');
            return;
        }

        this.isSubmitting = true;
        this.updateSubmitState();
        const activeIcon = activeCard.dataset.icon || '';

        try {
            const response = await fetch('/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    challenge_id: this.challengeId,
                    selected_icon: activeIcon,
                    current_index: this.currentIndex,
                }),
            });

            const data = await response.json();
            if (data.success) {
                this.showMessage(data.message, 'success');
                this.disableInteractions();
            } else {
                this.showMessage(data.message, 'error');
            }
        } catch (error) {
            console.error('Icon slider submission error:', error);
            this.showMessage('An error occurred. Please try again.', 'error');
        } finally {
            this.isSubmitting = false;
            this.updateSubmitState();
        }
    }

    disableInteractions() {
        if (this.submitBtn) {
            this.submitBtn.disabled = true;
            this.submitBtn.textContent = 'Completed';
            this.submitBtn.style.cursor = 'default';
        }
        if (this.navLeft) {
            this.navLeft.disabled = true;
            this.navLeft.style.opacity = '0.5';
        }
        if (this.navRight) {
            this.navRight.disabled = true;
            this.navRight.style.opacity = '0.5';
        }
        if (this.dots && this.dots.length) {
            this.dots.forEach((dot) => {
                dot.disabled = true;
                dot.style.cursor = 'default';
                dot.style.opacity = '0.6';
            });
        }
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

            const left =
                availableWidth <= 0
                    ? Math.max(0, (viewportWidth - width) / 2)
                    : margin + this.randomPosition.leftRatio * availableWidth;

            const top =
                availableHeight <= 0
                    ? Math.max(0, (viewportHeight - height) / 2)
                    : margin + this.randomPosition.topRatio * availableHeight;

            this.container.style.left = `${left}px`;
            this.container.style.top = `${top}px`;
        };

        requestAnimationFrame(() => {
            applyPosition();
            setTimeout(applyPosition, 250);
        });
    }

    showMessage(text, type) {
        if (!this.messageDiv) {
            return;
        }
        this.messageDiv.textContent = text;
        this.messageDiv.className = `captcha-message ${type}`;
        this.messageDiv.classList.add('show');
        if (type === 'success') {
            setTimeout(() => {
                this.messageDiv.classList.remove('show');
            }, 3000);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new IconSliderCaptcha();
});
