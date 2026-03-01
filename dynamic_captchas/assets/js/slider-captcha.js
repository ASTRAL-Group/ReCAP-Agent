/**
 * Slider CAPTCHA JavaScript
 * Handles drag interaction, puzzle visualization, and submission.
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

class SliderCaptchaManager {
    constructor() {
        this.challengeId = null;
        this.isSubmitting = false;
        this.isDragging = false;
        this.currentPosition = 0;
        this.currentLeft = 0;
        this.trackWidth = 0;
        this.handleWidth = 0;
        this.maxPosition = 0;
        this.targetPosition = 0;
        this.tolerance = 20;
        this.dragOffset = 0;

        this.puzzleWrapper = null;
        this.puzzleScene = null;
        this.puzzleHole = null;
        this.puzzlePiece = null;
        this.sliderProgress = null;
        this.submitBtn = null;
        this.messageDiv = null;
        this.container = null;
        this.positionInput = null;
        this.sliderHandle = null;
        this.sliderTrack = null;
        this.proximityIndicator = null;
        this.randomPosition = getStaticPositionRatios();
        this.scaleFactor = 1;
        this.originalTargetPosition = 0;
        this.originalTolerance = 20;
        this.normalizedPosition = 0;
        this.viewportResizeHandler = null;
        this.requiresSubmit = true;
        this.dragStartLeft = 0;
        this.dragMoved = false;

        this.puzzleWidth = 0;
        this.puzzleHeight = 0;
        this.pieceSize = 0;
        this.pieceTop = 0;
        this.holeLeft = 0;

        this.initializeElements();
        this.bindEvents();
        this.setupAnimations();
    }

    initializeElements() {
        this.sliderHandle = document.getElementById('slider-handle');
        this.sliderTrack = document.getElementById('slider-track');
        this.sliderProgress = document.getElementById('slider-progress');
        this.proximityIndicator = document.getElementById('proximity-indicator');
        this.submitBtn = document.getElementById('submit-btn');
        this.messageDiv = document.getElementById('message');
        this.container = document.querySelector('.captcha-container');
        this.positionInput = document.getElementById('slider-position');
        if (this.container) {
            const attr = (this.container.dataset && this.container.dataset.requiresSubmit) || 'true';
            this.requiresSubmit = attr.toLowerCase() !== 'false';
        }

        this.puzzleWrapper = document.getElementById('puzzle-wrapper');
        this.puzzleScene = document.getElementById('puzzle-scene');
        this.puzzleHole = document.getElementById('puzzle-hole');
        this.puzzlePiece = document.getElementById('puzzle-piece');

        if (!this.sliderHandle || !this.sliderTrack) {
            console.error('Slider CAPTCHA elements not found');
            return;
        }

        this.configurePuzzleFromDataset();
        this.updateScaledLayout();
        this.recalculateDimensions();

        const { targetPosition, tolerance } = this.sliderTrack.dataset;
        if (targetPosition) {
            this.setTargetPosition(parseFloat(targetPosition));
        }
        if (tolerance) {
            this.setTolerance(parseFloat(tolerance));
        }

        this.updateProximityIndicator(this.currentPosition);
        this.positionContainerRandomly();
    }

    configurePuzzleFromDataset() {
        if (!this.puzzleWrapper) return;

        const dataset = this.puzzleWrapper.dataset;
        this.puzzleWidth = parseFloat(dataset.puzzleWidth || '0');
        this.puzzleHeight = parseFloat(dataset.puzzleHeight || '0');
        this.pieceSize = parseFloat(dataset.pieceSize || '0');
        this.pieceTop = parseFloat(dataset.pieceTop || '0');
        this.holeLeft = parseFloat(dataset.holeLeft || '0');
        const backgroundUrl = dataset.backgroundUrl || '';

        if (this.puzzleScene) {
            this.puzzleScene.style.setProperty('--puzzle-image', backgroundUrl ? `url('${backgroundUrl}')` : '');
            if (this.puzzleWidth) {
                this.puzzleScene.style.width = `${this.puzzleWidth}px`;
            }
            if (this.puzzleHeight) {
                this.puzzleScene.style.height = `${this.puzzleHeight}px`;
            }
        }

        if (this.puzzlePiece) {
            this.puzzlePiece.style.width = `${this.pieceSize}px`;
            this.puzzlePiece.style.height = `${this.pieceSize}px`;
            this.puzzlePiece.style.top = `${this.pieceTop}px`;
            this.puzzlePiece.style.left = '0px';
            this.puzzlePiece.style.transform = 'translateX(0px)';
            if (backgroundUrl) {
                this.puzzlePiece.style.backgroundImage = `url('${backgroundUrl}')`;
            }
            if (this.puzzleHeight) {
                this.puzzlePiece.style.backgroundSize = `${this.puzzleWidth}px ${this.puzzleHeight}px`;
            } else {
                this.puzzlePiece.style.backgroundSize = `${this.puzzleWidth}px auto`;
            }
            this.puzzlePiece.style.backgroundPosition = `${-this.holeLeft}px ${-this.pieceTop}px`;
        }

        if (this.puzzleHole) {
            this.puzzleHole.style.width = `${this.pieceSize}px`;
            this.puzzleHole.style.height = `${this.pieceSize}px`;
            this.puzzleHole.style.top = `${this.pieceTop}px`;
            this.puzzleHole.style.left = `${this.holeLeft}px`;
        }

        if (this.sliderTrack && this.puzzleWidth) {
            this.sliderTrack.style.width = `${this.puzzleWidth}px`;
        }
    }

    updateScaledLayout() {
        if (!this.sliderTrack) return;

        const margin = 60;
        const viewportWidth = Math.max(window.innerWidth - margin, 260);
        const viewportHeight = Math.max(window.innerHeight - margin, 320);

        let scale = 1;

        if (this.puzzleWidth) {
            const widthScale = viewportWidth / this.puzzleWidth;
            if (Number.isFinite(widthScale)) {
                scale = Math.min(scale, widthScale);
            }
        }

        if (this.puzzleHeight) {
            const heightAllowance = viewportHeight - 260;
            if (heightAllowance > 0) {
                const heightScale = heightAllowance / this.puzzleHeight;
                if (Number.isFinite(heightScale)) {
                    scale = Math.min(scale, heightScale);
                }
            }
        }

        scale = Math.min(scale, 1);
        if (!Number.isFinite(scale) || scale <= 0) {
            scale = 1;
        }

        this.scaleFactor = scale;

        const scaledWidth = Math.round(this.puzzleWidth * this.scaleFactor);
        const scaledHeight = Math.round(this.puzzleHeight * this.scaleFactor);
        const scaledPieceSize = Math.round(this.pieceSize * this.scaleFactor);
        const scaledPieceTop = Math.round(this.pieceTop * this.scaleFactor);
        const scaledHoleLeft = Math.round(this.holeLeft * this.scaleFactor);

        if (this.puzzleWrapper) {
            if (scaledWidth) {
                this.puzzleWrapper.style.width = `${scaledWidth}px`;
            }
            if (scaledHeight) {
                this.puzzleWrapper.style.height = `${scaledHeight}px`;
            }
        }

        if (this.puzzleScene) {
            if (scaledWidth) {
                this.puzzleScene.style.width = `${scaledWidth}px`;
            }
            if (scaledHeight) {
                this.puzzleScene.style.height = `${scaledHeight}px`;
            }
            if (scaledWidth && scaledHeight) {
                this.puzzleScene.style.backgroundSize = `${scaledWidth}px ${scaledHeight}px`;
            }
        }

        if (this.puzzlePiece) {
            if (scaledPieceSize) {
                this.puzzlePiece.style.width = `${scaledPieceSize}px`;
                this.puzzlePiece.style.height = `${scaledPieceSize}px`;
            }
            this.puzzlePiece.style.top = `${scaledPieceTop}px`;
            this.puzzlePiece.style.transform = 'translateX(0px)';
            if (scaledWidth && scaledHeight) {
                this.puzzlePiece.style.backgroundSize = `${scaledWidth}px ${scaledHeight}px`;
            }
            this.puzzlePiece.style.backgroundPosition = `${-scaledHoleLeft}px ${-scaledPieceTop}px`;
        }

        if (this.puzzleHole) {
            if (scaledPieceSize) {
                this.puzzleHole.style.width = `${scaledPieceSize}px`;
                this.puzzleHole.style.height = `${scaledPieceSize}px`;
            }
            this.puzzleHole.style.top = `${scaledPieceTop}px`;
            this.puzzleHole.style.left = `${scaledHoleLeft}px`;
        }

        if (this.sliderTrack) {
            if (scaledWidth) {
                this.sliderTrack.style.width = `${scaledWidth}px`;
            }
            const baseHeight = parseFloat(this.sliderTrack.dataset.trackHeight || this.sliderTrack.style.height || 12);
            const scaledTrackHeight = Math.max(8, Math.round(baseHeight * this.scaleFactor));
            this.sliderTrack.style.height = `${scaledTrackHeight}px`;
        }

        if (this.sliderProgress) {
            this.sliderProgress.style.height = this.sliderTrack.style.height;
        }

        if (this.sliderHandle) {
            const baseSize = parseFloat(
                this.sliderTrack.dataset.sliderSize ||
                this.sliderHandle.dataset.baseSize ||
                this.sliderHandle.offsetWidth ||
                50
            );
            this.sliderHandle.dataset.baseSize = baseSize;
            const scaledHandle = Math.max(28, Math.round(baseSize * this.scaleFactor));
            this.sliderHandle.style.width = `${scaledHandle}px`;
            this.sliderHandle.style.height = `${scaledHandle}px`;
        }

        if (this.proximityIndicator) {
            this.proximityIndicator.style.height = `${Math.max(40, Math.round(60 * this.scaleFactor))}px`;
        }

        if (Number.isFinite(this.originalTargetPosition)) {
            this.targetPosition = this.originalTargetPosition * this.scaleFactor;
        }
        if (Number.isFinite(this.originalTolerance)) {
            this.tolerance = this.originalTolerance * this.scaleFactor;
        }

        const normalized = this.normalizedPosition || this.originalTargetPosition || 0;
        this.currentPosition = normalized * this.scaleFactor;
    }

    recalculateDimensions() {
        if (!this.sliderHandle || !this.sliderTrack) return;

        const trackRect = this.sliderTrack.getBoundingClientRect();
        const handleRect = this.sliderHandle.getBoundingClientRect();
        this.trackWidth = trackRect.width;
        this.handleWidth = handleRect.width;
        this.maxPosition = Math.max(0, this.trackWidth - this.handleWidth);

        const normalized = this.normalizedPosition || this.originalTargetPosition || 0;
        const desiredCenter = this.scaleFactor ? normalized * this.scaleFactor : normalized;
        const fallbackCenter = this.handleWidth / 2;
        this.updateSliderPosition(desiredCenter || fallbackCenter, { isCenter: true });

        if (this.positionInput) {
            this.positionInput.value = Math.round(this.normalizedPosition || 0);
        }
    }

    bindEvents() {
        if (!this.sliderHandle) return;

        this.boundDrag = (e) => this.drag(e);
        this.boundEndDrag = () => this.endDrag();

        this.sliderHandle.addEventListener('mousedown', (e) => this.startDrag(e));
        document.addEventListener('mousemove', this.boundDrag);
        document.addEventListener('mouseup', this.boundEndDrag);

        this.sliderHandle.addEventListener('touchstart', (e) => this.startDrag(e), { passive: false });
        document.addEventListener('touchmove', this.boundDrag, { passive: false });
        document.addEventListener('touchend', this.boundEndDrag);

        if (this.submitBtn) {
            this.submitBtn.addEventListener('click', () => this.handleSubmit());
        }

        this.sliderHandle.addEventListener('contextmenu', (e) => e.preventDefault());
        this.sliderHandle.addEventListener('selectstart', (e) => e.preventDefault());

        this.viewportResizeHandler = () => {
            this.updateScaledLayout();
            this.recalculateDimensions();
            this.positionContainerRandomly();
        };

        window.addEventListener('resize', this.viewportResizeHandler);
    }

    setupAnimations() {
        if (!this.container) return;

        this.container.style.opacity = '0';
        this.container.style.transform = 'translateY(20px)';

        setTimeout(() => {
            this.container.style.transition = 'all 0.6s ease';
            this.container.style.opacity = '1';
            this.container.style.transform = 'translateY(0)';
        }, 80);
    }
    
    positionContainerRandomly() {
        if (!this.container) {
            return;
        }

        const margin = 20;
        const applyPosition = () => {
            this.updateScaledLayout();
            this.recalculateDimensions();

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

    startDrag(event) {
        if (!this.sliderHandle || !this.sliderTrack || this.isSubmitting) return;

        event.preventDefault();
        event.stopPropagation();

        const clientX = this.getClientX(event);
        const trackRect = this.sliderTrack.getBoundingClientRect();
        this.dragOffset = this.handleWidth / 2;
        if (!Number.isFinite(this.dragOffset)) {
            this.dragOffset = this.handleWidth / 2;
        }
        const desired = clientX - trackRect.left - this.dragOffset;
        this.updateSliderPosition(desired);

        this.isDragging = true;
        this.dragMoved = false;
        this.dragStartLeft = this.currentLeft;
        this.sliderHandle.classList.add('dragging');
        if (this.puzzlePiece) {
            this.puzzlePiece.classList.add('dragging');
        }
        if (this.sliderTrack) {
            this.sliderTrack.classList.add('active');
        }
        document.body.style.cursor = 'grabbing';
        document.body.style.userSelect = 'none';
        document.body.style.webkitUserSelect = 'none';
    }

    drag(event) {
        if (!this.isDragging) return;

        event.preventDefault();
        event.stopPropagation();

        const trackRect = this.sliderTrack.getBoundingClientRect();
        const clientX = this.getClientX(event);
        let position = clientX - trackRect.left - this.dragOffset;

        this.updateSliderPosition(position);
        if (!this.dragMoved && Math.abs(this.currentLeft - this.dragStartLeft) >= 1) {
            this.dragMoved = true;
        }
    }

    endDrag() {
        if (!this.isDragging) return;

        this.isDragging = false;
        this.sliderHandle.classList.remove('dragging');
        if (this.puzzlePiece) {
            this.puzzlePiece.classList.remove('dragging');
        }
        if (this.sliderTrack) {
            this.sliderTrack.classList.remove('active');
        }

        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.body.style.webkitUserSelect = '';

        if (this.submitBtn) {
            this.submitBtn.disabled = false;
            this.submitBtn.style.opacity = '1';
            this.submitBtn.style.cursor = 'pointer';
        }

        this.updateProximityIndicator(this.currentPosition);

        const movedEnough = this.dragMoved || Math.abs(this.currentLeft - this.dragStartLeft) >= 1;
        if (!this.requiresSubmit && movedEnough) {
            setTimeout(() => {
                if (!this.isSubmitting) {
                    this.handleSubmit();
                }
            }, 120);
        }
    }

    updateSliderPosition(position, { isCenter = false } = {}) {
        if (!this.sliderHandle) return;

        let desiredLeft = isCenter ? position - this.handleWidth / 2 : position;
        if (!Number.isFinite(desiredLeft)) {
            desiredLeft = 0;
        }
        const clampedLeft = Math.max(0, Math.min(this.maxPosition, desiredLeft));
        this.currentLeft = clampedLeft;
        this.currentPosition = clampedLeft + this.handleWidth / 2;
        this.normalizedPosition = this.scaleFactor ? this.currentPosition / this.scaleFactor : this.currentPosition;

        this.sliderHandle.style.left = `${clampedLeft}px`;
        this.updatePuzzlePiecePosition(this.currentPosition);
        this.updateSliderProgress(this.currentPosition);
        this.updateProximityIndicator(this.currentPosition);

        if (this.positionInput) {
            this.positionInput.value = Math.round(this.normalizedPosition);
        }
    }

    updatePuzzlePiecePosition(center) {
        if (!this.puzzlePiece) return;
        const size = this.puzzlePiece.offsetWidth || (this.pieceSize * this.scaleFactor) || 0;
        if (!size) {
            this.puzzlePiece.style.transform = 'translateX(0px)';
            return;
        }
        const offset = center - size / 2;
        this.puzzlePiece.style.transform = `translateX(${offset}px)`;
    }

    updateSliderProgress(position) {
        if (!this.sliderProgress) return;

        const clamped = Math.max(0, Math.min(position, this.trackWidth));
        this.sliderProgress.style.width = `${clamped}px`;
    }

    updateProximityIndicator(centerPosition) {
        if (!this.proximityIndicator) return;

        const distance = Math.abs(centerPosition - this.targetPosition);

        if (distance <= this.tolerance) {
            this.proximityIndicator.classList.add('active');
            this.puzzlePiece?.classList.add('aligned');
            this.puzzleHole?.classList.add('glow');
        } else {
            this.proximityIndicator.classList.remove('active');
            this.puzzlePiece?.classList.remove('aligned');
            this.puzzleHole?.classList.remove('glow');
        }
    }

    getClientX(event) {
        if (event.touches && event.touches.length > 0) {
            return event.touches[0].clientX;
        }
        if (event.changedTouches && event.changedTouches.length > 0) {
            return event.changedTouches[0].clientX;
        }
        return event.clientX;
    }

    async handleSubmit() {
        if (this.isSubmitting) return;
        if (!this.challengeId) {
            const fallback = document.getElementById('challenge-id');
            if (fallback) {
                this.challengeId = fallback.value;
            }
        }
        if (!this.challengeId) {
            this.showMessage('Unable to submit the slider challenge. Please reload.', 'error');
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
                    slider_position: Math.round(this.normalizedPosition || 0),
                }),
            });

            const data = await response.json();

            if (data.success) {
                this.showMessage(data.message, 'success');
                if (this.submitBtn) {
                    this.submitBtn.disabled = true;
                }
                if (this.sliderHandle) {
                    this.sliderHandle.style.pointerEvents = 'none';
                }
                if (this.container) {
                    this.container.classList.add('solved');
                }
                this.createConfettiEffect();
            } else {
                this.showMessage(data.message, 'error');
                if (this.container) {
                    this.container.classList.add('shake');
                    setTimeout(() => {
                        this.container.classList.remove('shake');
                    }, 500);
                }
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
        if (!this.submitBtn) return;

        if (isSubmitting) {
            this.submitBtn.innerHTML = '<span class="captcha-loading"></span>Submitting...';
            this.submitBtn.disabled = true;
        } else {
            this.submitBtn.innerHTML = 'Submit';
            this.submitBtn.disabled = false;
        }
    }

    showMessage(text, type) {
        if (!this.messageDiv) return;

        this.messageDiv.textContent = text;
        this.messageDiv.className = `captcha-message ${type}`;
        this.messageDiv.classList.add('show');

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

    setChallengeId(id) {
        this.challengeId = id;
    }

    setTargetPosition(position) {
        this.originalTargetPosition = position;
        this.targetPosition = position * this.scaleFactor;
        if (!this.normalizedPosition) {
            this.normalizedPosition = position;
        }
        this.updateProximityIndicator(this.currentPosition);
    }

    setTolerance(value) {
        this.originalTolerance = value;
        this.tolerance = value * this.scaleFactor;
    }
}

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

    .captcha-loading {
        display: inline-block;
        width: 16px;
        height: 16px;
        border: 2px solid transparent;
        border-top: 2px solid currentColor;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-right: 8px;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

document.addEventListener('DOMContentLoaded', () => {
    window.sliderCaptchaManager = new SliderCaptchaManager();

    const challengeIdInput = document.getElementById('challenge-id');
    if (challengeIdInput) {
        window.sliderCaptchaManager.setChallengeId(challengeIdInput.value);
    }

    const sliderTrack = document.getElementById('slider-track');
    if (sliderTrack && sliderTrack.dataset.tolerance) {
        window.sliderCaptchaManager.tolerance = parseFloat(sliderTrack.dataset.tolerance);
    }

    if (sliderTrack && sliderTrack.dataset.targetPosition) {
        window.sliderCaptchaManager.setTargetPosition(parseFloat(sliderTrack.dataset.targetPosition));
    }
});
