/**
 * Career Catalyst — Home Page JavaScript
 * Handles scroll animations and animated stat counters
 */

document.addEventListener('DOMContentLoaded', () => {

    // =============================================
    // Intersection Observer — Scroll Animations
    // =============================================
    const animatedElements = document.querySelectorAll('.animate-on-scroll');

    if (animatedElements.length > 0) {
        const observerOptions = {
            root: null,
            rootMargin: '0px 0px -80px 0px',
            threshold: 0.1
        };

        const animationObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animated');
                    // Don't unobserve — animation only triggers once
                    animationObserver.unobserve(entry.target);
                }
            });
        }, observerOptions);

        animatedElements.forEach(el => {
            animationObserver.observe(el);
        });
    }

    // =============================================
    // Animated Stat Counters
    // =============================================
    const counters = document.querySelectorAll('.counter');

    if (counters.length > 0) {
        const counterObserverOptions = {
            root: null,
            rootMargin: '0px',
            threshold: 0.5
        };

        const animateCounter = (counterElement) => {
            const target = parseInt(counterElement.getAttribute('data-target'), 10);
            const duration = 2000; // 2 seconds
            const startTime = performance.now();

            const formatNumber = (num) => {
                if (num >= 1000) {
                    return num.toLocaleString();
                }
                return num.toString();
            };

            const updateCounter = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);

                // Ease-out cubic for smooth deceleration
                const easeOut = 1 - Math.pow(1 - progress, 3);
                const currentValue = Math.floor(easeOut * target);

                counterElement.textContent = formatNumber(currentValue);

                if (progress < 1) {
                    requestAnimationFrame(updateCounter);
                } else {
                    counterElement.textContent = formatNumber(target);
                }
            };

            requestAnimationFrame(updateCounter);
        };

        const counterObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    counterObserver.unobserve(entry.target);
                }
            });
        }, counterObserverOptions);

        counters.forEach(counter => {
            counterObserver.observe(counter);
        });
    }

    // =============================================
    // Parallax-lite effect on hero section
    // =============================================
    const heroSection = document.querySelector('.hero-section');

    if (heroSection) {
        window.addEventListener('scroll', () => {
            const scrolled = window.scrollY;
            if (scrolled < 800) {
                const heroImage = heroSection.querySelector('.hero-image-wrapper');
                if (heroImage) {
                    heroImage.style.transform = `translateY(${scrolled * 0.05}px)`;
                }
            }
        }, { passive: true });
    }

});
