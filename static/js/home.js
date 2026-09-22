/**
 * CareerCatalyst — Home Page JavaScript
 * Clean, lightweight, accessible.
 * Respects prefers-reduced-motion.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Respect user motion preferences
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
        return;
    }

    // Optional: Reveal animations handled smoothly by IntersectionObserver
    const revealElements = document.querySelectorAll('.animate-on-scroll');
    if (revealElements.length > 0 && 'IntersectionObserver' in window) {
        const revealObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animated');
                    revealObserver.unobserve(entry.target);
                }
            });
        }, {
            root: null,
            rootMargin: '0px 0px -40px 0px',
            threshold: 0.1
        });

        revealElements.forEach(el => revealObserver.observe(el));
    }
});
