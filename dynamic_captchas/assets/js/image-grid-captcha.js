/**
 * Image Grid JavaScript Handler
 * Handles checkbox interaction, challenge display, and tile selection
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

class ImageGridManager {
    constructor() {
        this.checkbox = null;
        this.challengeWrapper = null;
        this.imageGrid = null;
        this.verifyBtn = null;
        this.closeBtn = null;
        this.selectedTiles = [];
        this.isSubmitting = false;
        this.challengeId = null;
        this.instruction = '';
        this.correctTiles = [];
        this.container = null;
        this.randomPosition = getStaticPositionRatios();
        this.handleResize = null;
        this.challenge = null;
        this.challengeRandomPosition = getStaticPositionRatios();
        this.challengeResizeHandler = null;
        
        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        this.checkbox = document.getElementById('checkbox');
        this.challengeWrapper = document.getElementById('challenge-wrapper');
        this.imageGrid = document.getElementById('image-grid');
        this.verifyBtn = document.getElementById('verify-btn');
        this.closeBtn = document.getElementById('close-challenge');
        this.challengeId = document.getElementById('challenge-id').value;
        this.container = document.querySelector('.container');
        this.challenge = document.getElementById('challenge');
        this.positionContainerRandomly();

        console.log('Image Grid JavaScript loaded');
        console.log('Challenge ID:', this.challengeId);
    }

    bindEvents() {
        // Checkbox click handler
        if (this.checkbox) {
            this.checkbox.addEventListener('click', (e) => this.handleCheckboxClick(e));
            this.checkbox.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.handleCheckboxClick(e);
                }
            });
        }

        // Challenge buttons
        if (this.verifyBtn) {
            this.verifyBtn.addEventListener('click', (e) => this.handleVerify(e));
        }

        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', (e) => this.handleClose(e));
        }

        // Close challenge on background click
        if (this.challengeWrapper) {
            this.challengeWrapper.addEventListener('click', (e) => {
                if (e.target === this.challengeWrapper) {
                    this.handleClose(e);
                }
            });
        }
    }

    async handleCheckboxClick(e) {
        e.preventDefault();
        e.stopPropagation();

        if (this.checkbox.classList.contains('checked')) {
            return; // Already checked
        }

        // Check if challenge is already open
        if (this.challengeWrapper && this.challengeWrapper.classList.contains('show')) {
            return; // Challenge already open
        }

        console.log('Checkbox clicked, loading challenge...');

        // Show loading state
        this.checkbox.classList.add('loading');
        this.checkbox.setAttribute('aria-checked', 'true');
        
        const spinner = this.checkbox.querySelector('.checkbox-spinner');
        if (spinner) {
            spinner.style.display = 'block';
        }

        try {
            // Get challenge data from server
            const response = await fetch(`/challenge/image_grid/data/${this.challengeId}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || 'Failed to load challenge');
            }

            this.instruction = data.instruction;
            this.correctTiles = data.correct_tiles;
            
            // Generate image grid
            this.generateImageGrid(data.images);
            
            // Show challenge
            this.showChallenge();

        } catch (error) {
            console.error('Error loading challenge:', error);
            this.resetCheckbox();
        }
    }

    generateImageGrid(images) {
        if (!this.imageGrid) return;

        this.imageGrid.innerHTML = '';
        
        // Create 3x3 grid (9 tiles)
        for (let i = 0; i < 9; i++) {
            const tile = document.createElement('div');
            tile.className = 'image-tile';
            tile.dataset.index = i;
            tile.setAttribute('role', 'button');
            tile.setAttribute('tabindex', i + 1);
            tile.setAttribute('aria-label', `Image ${i + 1}`);

            const img = document.createElement('img');
            img.src = images[i] || this.generatePlaceholderImage(i);
            img.alt = `Challenge image ${i + 1}`;

            const overlay = document.createElement('div');
            overlay.className = 'image-tile-overlay';

            const checkbox = document.createElement('div');
            checkbox.className = 'image-tile-checkbox';
            checkbox.innerHTML = '✓';

            tile.appendChild(img);
            tile.appendChild(overlay);
            tile.appendChild(checkbox);

            // Add click handler
            tile.addEventListener('click', (e) => this.handleTileClick(e, i));
            tile.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.handleTileClick(e, i);
                }
            });

            this.imageGrid.appendChild(tile);
        }

        // Update instruction text
        const keywordElement = document.getElementById('challenge-keyword');
        if (keywordElement) {
            keywordElement.textContent = this.instruction;
        }
    }

    generatePlaceholderImage(index) {
        // Generate a simple placeholder image using canvas
        const canvas = document.createElement('canvas');
        canvas.width = 100;
        canvas.height = 100;
        const ctx = canvas.getContext('2d');
        
        // Create a simple pattern based on index
        const colors = ['#4285f4', '#34a853', '#fbbc04', '#ea4335', '#9aa0a6'];
        const color = colors[index % colors.length];
        
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, 100, 100);
        
        ctx.fillStyle = '#fff';
        ctx.font = '16px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(`Image ${index + 1}`, 50, 55);
        
        return canvas.toDataURL();
    }

    handleTileClick(e, index) {
        e.preventDefault();
        e.stopPropagation();

        const tile = e.currentTarget;
        const isSelected = this.selectedTiles.includes(index);

        if (isSelected) {
            // Deselect tile
            this.selectedTiles = this.selectedTiles.filter(i => i !== index);
            tile.classList.remove('selected');
        } else {
            // Select tile
            this.selectedTiles.push(index);
            tile.classList.add('selected');
        }

        console.log('Selected tiles:', this.selectedTiles);
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
            setTimeout(() => {
                applyPosition();
                this.positionChallengeRandomly();
            }, 250);
        });

        if (!this.handleResize) {
            this.handleResize = () => {
                applyPosition();
                this.positionChallengeRandomly();
            };
            window.addEventListener('resize', this.handleResize);
        }
    }

    positionChallengeRandomly() {
        if (!this.challenge || !this.challengeWrapper || !this.challengeWrapper.classList.contains('show')) {
            return;
        }

        // Ensure challenge is measurable
        this.challenge.style.position = 'absolute';

        const margin = 20;
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        const rect = this.challenge.getBoundingClientRect();
        const width = rect.width || this.challenge.offsetWidth;
        const height = rect.height || this.challenge.offsetHeight;

        const availableWidth = Math.max(0, viewportWidth - width - margin * 2);
        const availableHeight = Math.max(0, viewportHeight - height - margin * 2);

        const left = availableWidth <= 0
            ? Math.max(margin, (viewportWidth - width) / 2)
            : margin + this.challengeRandomPosition.leftRatio * availableWidth;

        const top = availableHeight <= 0
            ? Math.max(margin, (viewportHeight - height) / 2)
            : margin + this.challengeRandomPosition.topRatio * availableHeight;

        this.challenge.style.left = `${left}px`;
        this.challenge.style.top = `${top}px`;
    }


    showChallenge() {
        if (!this.challengeWrapper) return;

        this.challengeRandomPosition = getStaticPositionRatios();
        this.challengeWrapper.style.display = 'block';

        requestAnimationFrame(() => {
            this.challengeWrapper.classList.add('show');
            setTimeout(() => this.positionChallengeRandomly(), 40);
        });

        if (!this.challengeResizeHandler) {
            this.challengeResizeHandler = () => this.positionChallengeRandomly();
            window.addEventListener('resize', this.challengeResizeHandler);
        }
    }

    hideChallenge() {
        if (!this.challengeWrapper) return;

        this.challengeWrapper.classList.remove('show');

        setTimeout(() => {
            this.challengeWrapper.style.display = 'none';
        }, 300);

        if (this.challengeResizeHandler) {
            window.removeEventListener('resize', this.challengeResizeHandler);
            this.challengeResizeHandler = null;
        }
    }

    async handleVerify(e) {
        e.preventDefault();
        e.stopPropagation();

        if (this.isSubmitting) return;

        console.log('Verifying challenge...');
        this.isSubmitting = true;

        // Disable buttons during submission
        this.verifyBtn.disabled = true;
        this.verifyBtn.textContent = 'Verifying...';

        try {
            const response = await fetch('/verify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    challenge_id: this.challengeId,
                    selected_tiles: this.selectedTiles
                })
            });

            const data = await response.json();
            console.log('Verification response:', data);

            if (data.success) {
                // Success - mark checkbox as checked
                this.checkbox.classList.remove('loading');
                this.checkbox.classList.add('checked');
                this.checkbox.setAttribute('aria-checked', 'true');
                
                const spinner = this.checkbox.querySelector('.checkbox-spinner');
                const checkmark = this.checkbox.querySelector('.checkbox-checkmark');
                
                if (spinner) spinner.style.display = 'none';
                if (checkmark) checkmark.style.display = 'block';
                
                this.hideChallenge();
                
                // Show success message
                this.showMessage('Image Grid verification successful!', 'success');
                
            } else {
                // Failed - keep window open, reset tiles, and show error
                this.showMessage(data.message || 'Verification failed. Please try again.', 'error');
                // this.resetTilesOnly();  // Commented out to preserve tile selections for self-correction training
                // this.resetCheckboxState();  // Commented out to preserve checkbox state for self-correction training

                // Re-enable verify button
                this.verifyBtn.disabled = false;
                this.verifyBtn.textContent = 'Verify';
            }

        } catch (error) {
            console.error('Verification error:', error);
            this.showMessage('An error occurred during verification. Please try again.', 'error');
            // this.resetTilesOnly();  // Commented out to preserve tile selections for self-correction training
            // this.resetCheckboxState();  // Commented out to preserve checkbox state for self-correction training

            // Re-enable verify button
            this.verifyBtn.disabled = false;
            this.verifyBtn.textContent = 'Verify';
        } finally {
            this.isSubmitting = false;
        }
    }


    handleClose(e) {
        e.preventDefault();
        e.stopPropagation();
        
        console.log('Closing challenge...');
        this.hideChallenge();
        this.resetCheckbox();
    }

    resetChallenge() {
        this.selectedTiles = [];
        this.hideChallenge();
        
        // Reset all tiles
        const tiles = this.imageGrid.querySelectorAll('.image-tile');
        tiles.forEach(tile => {
            tile.classList.remove('selected');
        });
        
    }

    resetTilesOnly() {
        // Reset tile selections but keep challenge window open
        this.selectedTiles = [];
        
        // Reset all tiles
        const tiles = this.imageGrid.querySelectorAll('.image-tile');
        tiles.forEach(tile => {
            tile.classList.remove('selected');
        });
        
        // Reset verify button state
        if (this.verifyBtn) {
            this.verifyBtn.disabled = false;
            this.verifyBtn.textContent = 'Verify';
        }
    }

    resetCheckbox() {
        this.checkbox.classList.remove('loading', 'checked');
        this.checkbox.setAttribute('aria-checked', 'false');
        
        const spinner = this.checkbox.querySelector('.checkbox-spinner');
        const checkmark = this.checkbox.querySelector('.checkbox-checkmark');
        
        if (spinner) spinner.style.display = 'none';
        if (checkmark) checkmark.style.display = 'none';
    }

    resetCheckboxState() {
        // Reset checkbox to allow clicking again (but keep challenge window open)
        this.checkbox.classList.remove('loading');
        this.checkbox.setAttribute('aria-checked', 'false');
        
        const spinner = this.checkbox.querySelector('.checkbox-spinner');
        if (spinner) spinner.style.display = 'none';
        
        // Make checkbox clickable again
        this.checkbox.style.pointerEvents = 'auto';
        this.checkbox.style.cursor = 'pointer';
    }

    showMessage(text, type) {
        // Create a simple message display
        let messageDiv = document.getElementById('message');
        if (!messageDiv) {
            messageDiv = document.createElement('div');
            messageDiv.id = 'message';
            messageDiv.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 4px;
                color: white;
                font-weight: 500;
                z-index: 10001;
                max-width: 300px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                transform: translateX(100%);
                transition: transform 0.3s ease;
            `;
            document.body.appendChild(messageDiv);
        }

        messageDiv.textContent = text;
        messageDiv.style.backgroundColor = type === 'success' ? '#34a853' : '#ea4335';
        messageDiv.style.transform = 'translateX(0)';

        // Auto-hide after 3 seconds
        setTimeout(() => {
            messageDiv.style.transform = 'translateX(100%)';
        }, 3000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if this is a Image Grid page
    if (document.querySelector('.container')) {
        window.ImageGridManager = new ImageGridManager();
    }
});
