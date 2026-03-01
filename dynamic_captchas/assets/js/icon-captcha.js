/**
 * Icon Selection CAPTCHA JavaScript
 * Handles icon selection, submission, and user interaction for icon-based CAPTCHAs
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

class IconCaptchaManager {
    constructor() {
        this.icons = null;
        this.submitBtn = null;
        this.messageDiv = null;
        this.selectedIcon = null;
        this.isSubmitting = false;
        this.container = null;
        this.randomPosition = getStaticPositionRatios();
        this.iconGrid = null;
        this.originalCanvasWidth = 0;
        this.originalCanvasHeight = 0;
        this.scaleFactor = 1;
        this.viewportResizeHandler = null;
        this.requiresSubmit = true;
        this.challengeId = null;

        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        this.icons = document.querySelectorAll('.icon-option');
        this.submitBtn = document.getElementById('submit-btn');
        this.messageDiv = document.getElementById('message');
        this.container = document.querySelector('.captcha-container');
        this.iconGrid = document.querySelector('.icon-grid');
        if (this.container) {
            const attr = (this.container.dataset && this.container.dataset.requiresSubmit) || 'true';
            this.requiresSubmit = attr.toLowerCase() !== 'false';
        }
        const challengeInput = document.getElementById('challenge-id');
        if (challengeInput) {
            this.challengeId = challengeInput.value;
        }

        if (this.iconGrid) {
            const widthMatch = this.iconGrid.style.width.match(/([\d.]+)/);
            const heightMatch = this.iconGrid.style.height.match(/([\d.]+)/);
            this.originalCanvasWidth = widthMatch ? parseFloat(widthMatch[1]) : this.iconGrid.getBoundingClientRect().width;
            this.originalCanvasHeight = heightMatch ? parseFloat(heightMatch[1]) : this.iconGrid.getBoundingClientRect().height;
            this.fitCanvasToViewport();
        }

        this.positionContainerRandomly();

        console.log('Icon CAPTCHA JavaScript loaded');
        console.log('Found', this.icons.length, 'icons');
        console.log('Submit button:', this.submitBtn);

        // Initialize submit button
        if (this.submitBtn) {
            this.submitBtn.disabled = true;
            this.submitBtn.style.opacity = '0.6';
            this.submitBtn.style.cursor = 'not-allowed';
        }
    }

    fitCanvasToViewport() {
        if (!this.iconGrid) {
            return;
        }

        if (!this.originalCanvasWidth) {
            const widthMatch = this.iconGrid.style.width.match(/([\d.]+)/);
            this.originalCanvasWidth = widthMatch ? parseFloat(widthMatch[1]) : this.iconGrid.getBoundingClientRect().width;
        }

        if (!this.originalCanvasHeight) {
            const heightMatch = this.iconGrid.style.height.match(/([\d.]+)/);
            this.originalCanvasHeight = heightMatch ? parseFloat(heightMatch[1]) : this.iconGrid.getBoundingClientRect().height;
        }

        const margin = 60;
        const availableWidth = Math.max(window.innerWidth - margin, 240);
        const availableHeight = Math.max(window.innerHeight - 180, 220);

        let scale = 1;
        if (this.originalCanvasWidth) {
            scale = Math.min(scale, availableWidth / this.originalCanvasWidth);
        }
        if (this.originalCanvasHeight) {
            scale = Math.min(scale, availableHeight / this.originalCanvasHeight);
        }

        if (!Number.isFinite(scale) || scale <= 0) {
            scale = 1;
        }
        scale = Math.min(scale, 1);
        this.scaleFactor = scale;

        const scaledWidth = Math.round(this.originalCanvasWidth * this.scaleFactor);
        const scaledHeight = Math.round(this.originalCanvasHeight * this.scaleFactor);

        this.iconGrid.style.width = `${scaledWidth}px`;
        this.iconGrid.style.height = `${scaledHeight}px`;

        if (this.icons && this.icons.length > 0) {
            this.icons.forEach((icon) => {
                const baseX = parseFloat(icon.dataset.x || '0');
                const baseY = parseFloat(icon.dataset.y || '0');
                const baseSize = parseFloat(icon.dataset.size || '60');
                const scaledX = Math.round(baseX * this.scaleFactor);
                const scaledY = Math.round(baseY * this.scaleFactor);
                const scaledSize = Math.max(24, Math.round(baseSize * this.scaleFactor));

                icon.style.left = `${scaledX}px`;
                icon.style.top = `${scaledY}px`;
                icon.style.width = `${scaledSize}px`;
                icon.style.height = `${scaledSize}px`;

                const iconElement = icon.querySelector('i');
                if (iconElement) {
                    iconElement.style.fontSize = `${Math.max(18, Math.round(scaledSize * 0.6))}px`;
                }
            });
        }
    }

    bindEvents() {
        // Set up canvas click handler (entire canvas is clickable)
        const canvas = this.iconGrid;
        if (canvas) {
            canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
            canvas.style.cursor = 'crosshair'; // Show crosshair cursor to indicate clickable area
        }

        // Set up submit button handler
        if (this.submitBtn) {
            this.submitBtn.addEventListener('click', (e) => this.handleSubmit(e));
        }

        if (!this.viewportResizeHandler) {
            this.viewportResizeHandler = () => {
                this.fitCanvasToViewport();
                this.positionContainerRandomly();
            };
            window.addEventListener('resize', this.viewportResizeHandler);
        }

        // Debug: Log all elements
        console.log('All elements found:');
        console.log('- Icons:', this.icons.length);
        console.log('- Submit button:', this.submitBtn);
        console.log('- Message div:', this.messageDiv);
        console.log('- Challenge ID input:', document.getElementById('challenge-id'));
        console.log('- Selected icon input:', document.getElementById('selected-icon'));
        console.log('- Canvas:', canvas);
    }

    handleCanvasClick(e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('Canvas clicked');
        
        // Get click position relative to the canvas
        const canvas = document.querySelector('.icon-grid');
        const canvasRect = canvas.getBoundingClientRect();
        const clickX = e.clientX - canvasRect.left;
        const clickY = e.clientY - canvasRect.top;
        const originalX = this.scaleFactor ? clickX / this.scaleFactor : clickX;
        const originalY = this.scaleFactor ? clickY / this.scaleFactor : clickY;

        // Store click position for validation
        this.lastClickPosition = {
            scaledX: clickX,
            scaledY: clickY,
            originalX,
            originalY,
            canvasRect: canvasRect
        };
        
        // Remove previous selection and click ticks
        this.icons.forEach(icon => {
            icon.classList.remove('selected');
        });
        this.removeClickTicks();
        
        // Clear any previous selection
        this.selectedIcon = null;
        
        // Show tick mark at actual click position
        this.showClickTick(clickX, clickY);
        
        // Update hidden input (will be empty since we don't know which icon was clicked)
        const hiddenInput = document.getElementById('selected-icon');
        if (hiddenInput) {
            hiddenInput.value = '';
        }
        
        // Enable submit button (user can submit their click position)
        if (this.submitBtn) {
            this.submitBtn.disabled = false;
            this.submitBtn.style.opacity = '1';
            this.submitBtn.style.cursor = 'pointer';
            this.submitBtn.style.backgroundColor = '';
        }
        
        console.log('Canvas clicked at position:', clickX, clickY, 'Submit button enabled');
        
        if (!this.requiresSubmit) {
            setTimeout(() => {
                if (!this.isSubmitting) {
                    this.handleSubmit();
                }
            }, 150);
        }
    }

    async handleSubmit(e) {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        console.log('Submission triggered, lastClickPosition:', this.lastClickPosition);
        
        if (!this.lastClickPosition) {
            console.log('No click position recorded');
            this.showMessage('Please click on the canvas first.', 'error');
            return;
        }

        if (this.isSubmitting) {
            console.log('Already submitting, ignoring click');
            return;
        }

        const challengeIdInput = this.challengeId || (document.getElementById('challenge-id') && document.getElementById('challenge-id').value) || '';
        if (!challengeIdInput) {
            console.error('Missing challenge ID for icon CAPTCHA submission.');
            this.showMessage('Unable to submit right now. Please reload the CAPTCHA.', 'error');
            return;
        }
        this.challengeId = challengeIdInput;
        console.log('Submitting with challenge ID:', this.challengeId, 'click position:', this.lastClickPosition);
        
        this.isSubmitting = true;
        
        // Disable button during submission
        if (this.submitBtn) {
            this.submitBtn.disabled = true;
            this.submitBtn.style.opacity = '0.6';
            this.submitBtn.textContent = 'Submitting...';
        }
        
        try {
            // Prepare click position data for validation
            const clickData = {
                challenge_id: this.challengeId,
                selected_icon: this.selectedIcon || '' // Will be empty since we don't know which icon was clicked
            };
            
            // Add canvas click position if available
            if (this.lastClickPosition) {
                clickData.click_position = {
                    x: Math.round(this.lastClickPosition.originalX),
                    y: Math.round(this.lastClickPosition.originalY)
                };
                console.log('DEBUG: Sending click position (original coordinates):', clickData.click_position);
            }
            
            const response = await fetch('/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(clickData)
            });

            const data = await response.json();
            console.log('Response received:', data);

            if (data.success) {
                this.showMessage(data.message, 'success');
                this.icons.forEach(icon => {
                    icon.style.pointerEvents = 'none';
                    icon.style.cursor = 'default';
                });
                if (this.submitBtn) {
                    this.submitBtn.disabled = true;
                    this.submitBtn.textContent = 'Completed';
                }
            } else {
                this.showMessage(data.message, 'error');
                this.resetSubmitButton();
                // this.resetSelection();  // Commented out to preserve selections for self-correction training
            }
        } catch (error) {
            console.error('Submission error:', error);
            this.showMessage('An error occurred. Please try again.', 'error');
            this.resetSubmitButton();
        } finally {
            this.isSubmitting = false;
        }
    }

    resetSelection() {
        // Reset selection
        this.icons.forEach(icon => {
            icon.classList.remove('selected');
        });
        this.selectedIcon = null;
        this.lastClickPosition = null; // Clear click position
        this.removeClickTicks(); // Remove click ticks
        const hiddenInput = document.getElementById('selected-icon');
        if (hiddenInput) {
            hiddenInput.value = '';
        }
        this.resetSubmitButton();
    }

    resetSubmitButton() {
        if (!this.submitBtn) {
            return;
        }
        this.submitBtn.disabled = true;
        this.submitBtn.style.opacity = '0.6';
        this.submitBtn.style.cursor = 'not-allowed';
        this.submitBtn.textContent = 'Submit';
    }

    positionContainerRandomly() {
        if (!this.container) {
            return;
        }

        const margin = 20;
        const applyPosition = () => {
            this.fitCanvasToViewport();
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
    }

    showMessage(text, type) {
        if (this.messageDiv) {
            this.messageDiv.textContent = text;
            this.messageDiv.className = `captcha-message ${type}`;
            this.messageDiv.classList.add('show');
            
            // Auto-hide success messages
            if (type === 'success') {
                setTimeout(() => {
                    this.messageDiv.classList.remove('show');
                }, 3000);
            }
        }
    }

    showClickTick(x, y) {
        // Remove any existing click ticks
        this.removeClickTicks();
        
        // Create tick mark element
        const tick = document.createElement('div');
        tick.className = 'click-tick';
        tick.style.cssText = `
            position: absolute;
            left: ${x - 12}px;
            top: ${y - 12}px;
            width: 24px;
            height: 24px;
            background: #48bb78;
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: bold;
            box-shadow: 0 2px 8px rgba(72, 187, 120, 0.4);
            border: 2px solid white;
            z-index: 20;
            pointer-events: none;
            animation: tickAppear 0.3s ease-out;
        `;
        tick.textContent = '✓';
        
        // Add to canvas
        const canvas = document.querySelector('.icon-grid');
        if (canvas) {
            canvas.appendChild(tick);
        }
    }

    removeClickTicks() {
        const existingTicks = document.querySelectorAll('.click-tick');
        existingTicks.forEach(tick => tick.remove());
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if this is an icon CAPTCHA page
    if (document.querySelector('.icon-captcha')) {
        window.iconCaptchaManager = new IconCaptchaManager();
    }
});
