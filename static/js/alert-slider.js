(() => {
    const sliderRoots = document.querySelectorAll('[data-alert-slider-root]');

    sliderRoots.forEach((root) => {
        const rail = root.querySelector('[data-alert-slider]');
        const slides = Array.from(root.querySelectorAll('[data-alert-slide]'));
        const previousButton = root.querySelector('[data-alert-previous]');
        const nextButton = root.querySelector('[data-alert-next]');
        const position = root.querySelector('[data-alert-position]');
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const autoplay = root.dataset.alertAutoplay === 'true';
        const interval = Number(root.dataset.alertInterval) || 6000;
        let activeIndex = 0;
        let timer = null;
        let scrollTimer = null;

        if (!rail || slides.length === 0) return;

        const updatePosition = () => {
            if (position) position.textContent = `${activeIndex + 1} / ${slides.length}`;
        };

        const showSlide = (index, behavior = 'smooth') => {
            activeIndex = (index + slides.length) % slides.length;
            rail.scrollTo({
                left: slides[activeIndex].offsetLeft - rail.offsetLeft,
                behavior: prefersReducedMotion ? 'auto' : behavior,
            });
            updatePosition();
        };

        const stop = () => {
            if (timer) window.clearInterval(timer);
            timer = null;
        };

        const start = () => {
            stop();
            if (autoplay && !prefersReducedMotion && slides.length > 1 && !document.hidden) {
                timer = window.setInterval(() => showSlide(activeIndex + 1), interval);
            }
        };

        previousButton?.addEventListener('click', () => {
            showSlide(activeIndex - 1);
            start();
        });
        nextButton?.addEventListener('click', () => {
            showSlide(activeIndex + 1);
            start();
        });
        rail.addEventListener('scroll', () => {
            window.clearTimeout(scrollTimer);
            scrollTimer = window.setTimeout(() => {
                const railStart = rail.offsetLeft + rail.scrollLeft;
                activeIndex = slides.reduce((closestIndex, slide, index) => (
                    Math.abs(slide.offsetLeft - railStart) < Math.abs(slides[closestIndex].offsetLeft - railStart)
                        ? index
                        : closestIndex
                ), activeIndex);
                updatePosition();
            }, 120);
        }, { passive: true });
        root.addEventListener('mouseenter', stop);
        root.addEventListener('mouseleave', start);
        root.addEventListener('focusin', stop);
        root.addEventListener('focusout', (event) => {
            if (!root.contains(event.relatedTarget)) start();
        });
        rail.addEventListener('pointerdown', stop);
        rail.addEventListener('pointerup', start);
        document.addEventListener('visibilitychange', () => document.hidden ? stop() : start());
        window.addEventListener('resize', () => showSlide(activeIndex, 'auto'));

        if (slides.length < 2) {
            previousButton?.setAttribute('disabled', '');
            nextButton?.setAttribute('disabled', '');
        }

        updatePosition();
        start();
    });
})();
