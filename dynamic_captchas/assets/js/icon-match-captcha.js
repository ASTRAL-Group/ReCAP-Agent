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

class IconMatchCaptchaManager {
    constructor() {
        this.container = document.querySelector('.icon-match-captcha');
        if (!this.container) {
            return;
        }

        this.canvas = this.container.querySelector('.icon-match-grid');
        this.pieces = Array.from(this.container.querySelectorAll('.icon-piece'));
        this.messageDiv = document.getElementById('message');
        this.challengeIdInput = document.getElementById('challenge-id');

        this.challengeId = this.challengeIdInput ? this.challengeIdInput.value : null;
        this.requiresSubmit = false;

        this.draggingPiece = null;
        this.pointerId = null;
        this.dragOffset = { x: 0, y: 0 };
        this.canvasRect = null;
        this.scaleFactor = 1;
        this.originalCanvasWidth = 0;
        this.originalCanvasHeight = 0;
        this.matchResult = null;
        this.isSubmitting = false;
        this.isSolved = false;
        this.randomPosition = getStaticPositionRatios();

        this.initialize();
    }

    initialize() {
        if (!this.canvas) {
            return;
        }

        // Determine base canvas size before scaling
        this.originalCanvasWidth = this.canvas.getBoundingClientRect().width;
        this.originalCanvasHeight = this.canvas.getBoundingClientRect().height;

        this.fitCanvasToViewport();
        this.positionContainerRandomly();
        this.bindEvents();
    }

    bindEvents() {
        this.pieces.forEach((piece) => {
            piece.addEventListener('pointerdown', (event) => this.handlePointerDown(event, piece));
        });

        window.addEventListener('pointermove', (event) => this.handlePointerMove(event));
        window.addEventListener('pointerup', (event) => this.handlePointerUp(event));
        window.addEventListener('pointercancel', (event) => this.handlePointerCancel(event));

        window.addEventListener('resize', () => {
            this.fitCanvasToViewport();
            this.positionContainerRandomly();
        });
    }

    fitCanvasToViewport() {
        if (!this.canvas) {
            return;
        }

        const margin = 60;
        const availableWidth = Math.max(window.innerWidth - margin, 280);
        const availableHeight = Math.max(window.innerHeight - 180, 220);

        let scale = 1;
        if (this.originalCanvasWidth) {
            scale = Math.min(scale, availableWidth / this.originalCanvasWidth);
        }
        if (this.originalCanvasHeight) {
            scale = Math.min(scale, availableHeight / this.originalCanvasHeight);
        }

        scale = Math.min(scale || 1, 1);
        this.scaleFactor = scale <= 0 ? 1 : scale;

        const scaledWidth = Math.round(this.originalCanvasWidth * this.scaleFactor);
        const scaledHeight = Math.round(this.originalCanvasHeight * this.scaleFactor);
        this.canvas.style.width = `${scaledWidth}px`;
        this.canvas.style.height = `${scaledHeight}px`;

        this.pieces.forEach((piece) => {
            const baseX = parseFloat(piece.dataset.x || '0');
            const baseY = parseFloat(piece.dataset.y || '0');
            const baseSize = parseFloat(piece.dataset.size || '60');

            const scaledX = Math.round(baseX * this.scaleFactor);
            const scaledY = Math.round(baseY * this.scaleFactor);
            const scaledSize = Math.max(28, Math.round(baseSize * this.scaleFactor));

            piece.style.left = `${scaledX}px`;
            piece.style.top = `${scaledY}px`;
            piece.style.width = `${scaledSize}px`;
            piece.style.height = `${scaledSize}px`;

            const iconElement = piece.querySelector('i');
            if (iconElement) {
                iconElement.style.fontSize = `${Math.max(20, Math.round(scaledSize * 0.65))}px`;
            }
        });

        this.canvasRect = this.canvas.getBoundingClientRect();
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
            setTimeout(applyPosition, 200);
        });
    }

    handlePointerDown(event, piece) {
        if (this.matchResult || this.isSolved) {
            return;
        }

        event.preventDefault();
        this.draggingPiece = piece;
        this.pointerId = event.pointerId;
        this.canvasRect = this.canvas.getBoundingClientRect();

        const rect = piece.getBoundingClientRect();
        this.dragOffset = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top,
        };

        piece.classList.add('dragging');
        piece.setPointerCapture?.(event.pointerId);
    }

    handlePointerMove(event) {
        if (!this.draggingPiece || event.pointerId !== this.pointerId) {
            return;
        }

        event.preventDefault();

        const newLeft = event.clientX - this.canvasRect.left - this.dragOffset.x;
        const newTop = event.clientY - this.canvasRect.top - this.dragOffset.y;

        const clamped = this.clampToCanvas(newLeft, newTop, this.draggingPiece);
        this.draggingPiece.style.left = `${Math.round(clamped.left)}px`;
        this.draggingPiece.style.top = `${Math.round(clamped.top)}px`;
    }

    handlePointerUp(event) {
        if (!this.draggingPiece || event.pointerId !== this.pointerId) {
            return;
        }

        event.preventDefault();

        const sourcePiece = this.draggingPiece;
        const targetPiece = this.findMatchingTwin(sourcePiece);

        sourcePiece.classList.remove('dragging');
        sourcePiece.releasePointerCapture?.(event.pointerId);

        if (targetPiece && this.arePiecesOverlapping(sourcePiece, targetPiece)) {
            const dropCenter = this.getPieceCenter(sourcePiece);
            const originalDrop = {
                x: Math.round(dropCenter.x / this.scaleFactor),
                y: Math.round(dropCenter.y / this.scaleFactor),
            };

            this.matchResult = {
                source_id: sourcePiece.dataset.iconId,
                target_id: targetPiece.dataset.iconId,
                drop_position: originalDrop,
            };

            this.handleSuccessfulMatch(sourcePiece, targetPiece);
        } else if (targetPiece) {
            this.showMessage('Line up the icon directly over its twin.', 'info');
        }

        this.draggingPiece = null;
        this.pointerId = null;
    }

    handlePointerCancel(event) {
        if (this.draggingPiece && event.pointerId === this.pointerId) {
            this.resetPiecePosition(this.draggingPiece);
            this.draggingPiece.classList.remove('dragging');
            this.draggingPiece = null;
            this.pointerId = null;
        }
    }

    clampToCanvas(left, top, piece) {
        const rect = piece.getBoundingClientRect();
        const width = rect.width || parseFloat(piece.style.width) || 50;
        const height = rect.height || parseFloat(piece.style.height) || 50;

        const maxLeft = (this.canvasRect.width || this.canvas.clientWidth) - width;
        const maxTop = (this.canvasRect.height || this.canvas.clientHeight) - height;

        return {
            left: Math.min(Math.max(0, left), maxLeft),
            top: Math.min(Math.max(0, top), maxTop),
        };
    }

    resetPiecePosition(piece) {
        const baseX = parseFloat(piece.dataset.x || '0');
        const baseY = parseFloat(piece.dataset.y || '0');
        piece.style.left = `${Math.round(baseX * this.scaleFactor)}px`;
        piece.style.top = `${Math.round(baseY * this.scaleFactor)}px`;
    }

    findMatchingTwin(piece) {
        const group = piece.dataset.matchGroup;
        if (!group) {
            return null;
        }
        return this.pieces.find(
            (candidate) => candidate !== piece && candidate.dataset.matchGroup === group,
        );
    }

    arePiecesOverlapping(pieceA, pieceB) {
        const rectA = this.getRelativeRect(pieceA);
        const rectB = this.getRelativeRect(pieceB);

        const centerA = {
            x: rectA.left + rectA.width / 2,
            y: rectA.top + rectA.height / 2,
        };
        const centerB = {
            x: rectB.left + rectB.width / 2,
            y: rectB.top + rectB.height / 2,
        };

        const deltaX = centerA.x - centerB.x;
        const deltaY = centerA.y - centerB.y;
        const distance = Math.hypot(deltaX, deltaY);
        const overlapThreshold = Math.min(rectA.width, rectA.height) * 0.45;

        return distance <= overlapThreshold;
    }

    getPieceCenter(piece) {
        const rect = this.getRelativeRect(piece);
        return {
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
        };
    }

    getRelativeRect(piece) {
        const pieceRect = piece.getBoundingClientRect();
        const canvasRect = this.canvas.getBoundingClientRect();
        return {
            left: pieceRect.left - canvasRect.left,
            top: pieceRect.top - canvasRect.top,
            width: pieceRect.width,
            height: pieceRect.height,
        };
    }

    handleSuccessfulMatch(sourcePiece, targetPiece) {
        sourcePiece.classList.add('matched');
        targetPiece.classList.add('matched');
        this.pieces.forEach((piece) => {
            piece.style.pointerEvents = 'none';
        });

        this.showMessage('Nice work! Verifying...', 'success');
        this.submitMatchAttempt();
    }

    async submitMatchAttempt() {
        if (!this.challengeId || !this.matchResult || this.isSubmitting) {
            return;
        }

        this.isSubmitting = true;

        try {
            const response = await fetch('/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    challenge_id: this.challengeId,
                    match_attempt: this.matchResult,
                }),
            });

            const data = await response.json();
            if (data.success) {
                this.showMessage(data.message, 'success');
                this.isSolved = true;
            } else {
                this.showMessage(data.message, 'error');
                // this.resetAllPieces();  // Commented out to preserve piece positions for self-correction training
                this.matchResult = null;
            }
        } catch (error) {
            console.error('Icon match submission failed', error);
            this.showMessage('Network error. Please try again.', 'error');
        } finally {
            this.isSubmitting = false;
        }
    }

    resetAllPieces() {
        this.pieces.forEach((piece) => {
            piece.style.pointerEvents = 'auto';
            piece.classList.remove('matched', 'dragging');
            this.resetPiecePosition(piece);
        });
        this.isSolved = false;
    }

    showMessage(text, type = 'info') {
        if (!this.messageDiv) {
            return;
        }
        this.messageDiv.textContent = text;
        this.messageDiv.className = `captcha-message ${type}`;
        this.messageDiv.classList.add('show');

        if (type === 'success') {
            setTimeout(() => this.messageDiv.classList.remove('show'), 3000);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new IconMatchCaptchaManager();
});
