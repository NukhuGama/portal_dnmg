/* Accessible, reusable slider for horizontally scrolling content rails. */
(function () {
    'use strict';

    function initializeSlider(slider) {
        const rail = slider.querySelector('[data-municipality-rail]');
        const buttons = slider.querySelectorAll('[data-condition-scroll]');
        const slides = slider.querySelectorAll('[data-municipality-slide]');
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        let autoplayTimer;
        let paused = reducedMotion;

        if (!rail || !slides.length) {
            return;
        }

        function hasOverflow() {
            return rail.scrollWidth > rail.clientWidth + 2;
        }

        function scrollToNext(direction) {
            if (!hasOverflow()) {
                return;
            }

            const distance = Math.max(rail.clientWidth * 0.82, slides[0].clientWidth + 12);
            const atEnd = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 4;
            const atStart = rail.scrollLeft <= 4;
            let target = rail.scrollLeft + direction * distance;

            if (direction > 0 && atEnd) {
                target = 0;
            } else if (direction < 0 && atStart) {
                target = rail.scrollWidth - rail.clientWidth;
            }

            rail.scrollTo({
                left: target,
                behavior: reducedMotion ? 'auto' : 'smooth',
            });
        }

        function stopAutoplay() {
            window.clearTimeout(autoplayTimer);
        }

        function scheduleAutoplay() {
            stopAutoplay();
            if (paused || !hasOverflow()) {
                return;
            }

            autoplayTimer = window.setTimeout(function () {
                scrollToNext(1);
                scheduleAutoplay();
            }, 5500);
        }

        buttons.forEach(function (button) {
            button.addEventListener('click', function () {
                scrollToNext(button.dataset.conditionScroll === 'next' ? 1 : -1);
                scheduleAutoplay();
            });
        });

        slider.addEventListener('mouseenter', function () {
            paused = true;
            stopAutoplay();
        });
        slider.addEventListener('mouseleave', function () {
            paused = reducedMotion;
            scheduleAutoplay();
        });
        slider.addEventListener('focusin', function () {
            paused = true;
            stopAutoplay();
        });
        slider.addEventListener('focusout', function (event) {
            if (!slider.contains(event.relatedTarget)) {
                paused = reducedMotion;
                scheduleAutoplay();
            }
        });
        slider.addEventListener('touchstart', function () {
            paused = true;
            stopAutoplay();
        }, { passive: true });
        slider.addEventListener('touchend', function () {
            paused = reducedMotion;
            scheduleAutoplay();
        }, { passive: true });
        document.addEventListener('visibilitychange', function () {
            paused = reducedMotion || document.hidden;
            scheduleAutoplay();
        });
        window.addEventListener('resize', scheduleAutoplay);

        scheduleAutoplay();
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-municipality-slider]').forEach(initializeSlider);
    });
})();
