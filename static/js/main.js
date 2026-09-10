/**
 * Career Catalyst — Main JavaScript
 * Handles global functionality: navbar scroll effect, smooth scrolling
 */

document.addEventListener('DOMContentLoaded', () => {

    // =============================================
    // Dark/Light Theme Toggle Switcher
    // =============================================
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    
    // Check initial theme from localStorage
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    if (themeIcon) {
        if (savedTheme === 'dark') {
            themeIcon.className = 'bi bi-sun-fill text-warning';
        } else {
            themeIcon.className = 'bi bi-moon-stars-fill text-secondary';
        }
    }
    
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const activeTheme = document.documentElement.getAttribute('data-theme');
            let newTheme = 'light';
            if (activeTheme === 'light') {
                newTheme = 'dark';
                themeIcon.className = 'bi bi-sun-fill text-warning';
            } else {
                themeIcon.className = 'bi bi-moon-stars-fill text-secondary';
            }
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }

    // =============================================
    // Navbar Scroll Effect
    // =============================================
    const navbar = document.getElementById('main-navbar');
    
    if (navbar) {
        const handleScroll = () => {
            if (window.scrollY > 50) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        };

        window.addEventListener('scroll', handleScroll, { passive: true });
        // Run once on load in case page is already scrolled
        handleScroll();
    }

    // =============================================
    // Smooth Scrolling for Anchor Links
    // =============================================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const targetId = this.getAttribute('href');
            
            // Skip if it's just "#" or empty
            if (targetId === '#' || targetId === '') return;

            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                e.preventDefault();
                
                const navbarHeight = navbar ? navbar.offsetHeight : 0;
                const targetPosition = targetElement.getBoundingClientRect().top + window.pageYOffset - navbarHeight - 20;

                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });

                // Close mobile nav if open
                const navbarCollapse = document.querySelector('.navbar-collapse.show');
                if (navbarCollapse) {
                    const bsCollapse = bootstrap.Collapse.getInstance(navbarCollapse);
                    if (bsCollapse) {
                        bsCollapse.hide();
                    }
                }
            }
        });
    });

    // =============================================
    // Active Nav Link Highlighting on Scroll
    // =============================================
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link[href^="#"]');

    if (sections.length > 0 && navLinks.length > 0) {
        const highlightNav = () => {
            const scrollPos = window.scrollY + 200;

            sections.forEach(section => {
                const sectionTop = section.offsetTop;
                const sectionHeight = section.offsetHeight;
                const sectionId = section.getAttribute('id');

                if (scrollPos >= sectionTop && scrollPos < sectionTop + sectionHeight) {
                    navLinks.forEach(link => {
                        link.classList.remove('active');
                        if (link.getAttribute('href') === `#${sectionId}`) {
                            link.classList.add('active');
                        }
                    });
                }
            });
        };

        window.addEventListener('scroll', highlightNav, { passive: true });
    }

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
    // Security / Anti-Inspect & Right-Click Protection
    // =============================================
    // Disable right-click context menu across the website
    document.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        return false;
    });

    // Disable keyboard shortcuts for Inspect Element, View Source, and DevTools
    document.addEventListener('keydown', (e) => {
        // F12 key
        if (e.key === 'F12' || e.keyCode === 123) {
            e.preventDefault();
            return false;
        }

        const isCtrlOrCmd = e.ctrlKey || e.metaKey;

        // Ctrl+Shift+I (DevTools), Ctrl+Shift+J (Console), Ctrl+Shift+C (Inspect Element)
        if (isCtrlOrCmd && e.shiftKey && (e.key === 'I' || e.key === 'i' || e.key === 'J' || e.key === 'j' || e.key === 'C' || e.key === 'c' || e.keyCode === 73 || e.keyCode === 74 || e.keyCode === 67)) {
            e.preventDefault();
            return false;
        }

        // Ctrl+U (View Source)
        if (isCtrlOrCmd && (e.key === 'u' || e.key === 'U' || e.keyCode === 85)) {
            e.preventDefault();
            return false;
        }

        // Ctrl+S (Save Webpage)
        if (isCtrlOrCmd && (e.key === 's' || e.key === 'S' || e.keyCode === 83)) {
            e.preventDefault();
            return false;
        }
    });

    // =============================================
    // Show / Hide Password Toggle on Password Fields
    // =============================================
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        // Prevent duplicate wrappers
        if (input.closest('.password-toggle-wrapper')) return;

        // Create container wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'position-relative password-toggle-wrapper';

        // Insert wrapper into DOM and move input inside
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        // Reserve space on the right for the eye icon
        input.style.paddingRight = '2.75rem';

        // Create toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'btn btn-link position-absolute end-0 top-50 translate-middle-y text-muted text-decoration-none border-0 p-0 me-3 password-toggle-btn';
        toggleBtn.setAttribute('aria-label', 'Toggle password visibility');
        toggleBtn.setAttribute('tabindex', '-1');
        toggleBtn.innerHTML = '<i class="bi bi-eye-slash-fill fs-5"></i>';
        toggleBtn.style.zIndex = '5';
        toggleBtn.style.cursor = 'pointer';

        toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (input.type === 'password') {
                input.type = 'text';
                toggleBtn.innerHTML = '<i class="bi bi-eye-fill fs-5 text-primary"></i>';
                toggleBtn.setAttribute('aria-label', 'Hide password');
            } else {
                input.type = 'password';
                toggleBtn.innerHTML = '<i class="bi bi-eye-slash-fill fs-5"></i>';
                toggleBtn.setAttribute('aria-label', 'Show password');
            }
        });

        wrapper.appendChild(toggleBtn);
    });

    // =============================================
    // Top Navigation Progress Bar
    // =============================================
    const progressBar = {
        element: null,
        timer: null,
        currentProgress: 0,
        init() {
            if (!this.element) {
                this.element = document.createElement('div');
                this.element.id = 'top-progress-bar';
                document.body.appendChild(this.element);
            }
        },
        start() {
            this.init();
            if (this.timer) clearInterval(this.timer);
            this.currentProgress = 15;
            this.element.style.opacity = '1';
            this.element.style.width = '15%';

            this.timer = setInterval(() => {
                if (this.currentProgress < 75) {
                    this.currentProgress += Math.random() * 15;
                    this.element.style.width = `${Math.min(this.currentProgress, 75)}%`;
                } else if (this.currentProgress < 90) {
                    this.currentProgress += Math.random() * 3;
                    this.element.style.width = `${Math.min(this.currentProgress, 90)}%`;
                }
            }, 200);
        },
        done() {
            if (!this.element) return;
            if (this.timer) clearInterval(this.timer);
            this.element.style.width = '100%';
            setTimeout(() => {
                this.element.style.opacity = '0';
                setTimeout(() => {
                    this.element.style.width = '0%';
                    this.currentProgress = 0;
                }, 300);
            }, 200);
        }
    };
    window.ProgressBar = progressBar;

    // Trigger progress bar on internal link clicks
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        const target = link.getAttribute('target');

        // Check if it's an external link, anchor hash, or new tab
        if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:') || target === '_blank') {
            return;
        }

        // Check if same origin
        try {
            const url = new URL(link.href, window.location.origin);
            if (url.origin === window.location.origin && url.pathname !== window.location.pathname) {
                progressBar.start();
            }
        } catch (err) {
            // Ignore URL parse error
        }
    });

    // Trigger on form submissions
    document.addEventListener('submit', (e) => {
        if (!e.defaultPrevented) {
            progressBar.start();
        }
    });

    // Complete on page load or pageshow (back/forward cache)
    window.addEventListener('pageshow', () => {
        progressBar.done();
    });

    // =============================================
    // Toast Notification System
    // =============================================
    const toastContainer = document.getElementById('toast-container');

    const initToast = (toastEl) => {
        if (!toastEl) return;
        const closeBtn = toastEl.querySelector('.toast-close-btn');
        const progressEl = toastEl.querySelector('.toast-progress');
        const duration = parseInt(toastEl.getAttribute('data-auto-dismiss') || '4000', 10);

        let timeoutId = null;
        let isPaused = false;
        let startTime = Date.now();
        let remainingTime = duration;

        const dismiss = () => {
            if (toastEl.classList.contains('toast-hiding')) return;
            toastEl.classList.add('toast-hiding');
            setTimeout(() => {
                toastEl.remove();
            }, 300);
        };

        if (progressEl) {
            progressEl.style.transition = `transform ${duration}ms linear`;
            // Trigger animation in next frame
            requestAnimationFrame(() => {
                progressEl.style.transform = 'scaleX(0)';
            });
        }

        const startTimer = (time) => {
            startTime = Date.now();
            timeoutId = setTimeout(dismiss, time);
        };

        const pauseTimer = () => {
            if (timeoutId) {
                clearTimeout(timeoutId);
                remainingTime -= (Date.now() - startTime);
                isPaused = true;
                if (progressEl) {
                    const computedWidth = window.getComputedStyle(progressEl).transform;
                    progressEl.style.transition = 'none';
                    progressEl.style.transform = computedWidth;
                }
            }
        };

        const resumeTimer = () => {
            if (isPaused && remainingTime > 0) {
                isPaused = false;
                if (progressEl) {
                    progressEl.style.transition = `transform ${remainingTime}ms linear`;
                    progressEl.style.transform = 'scaleX(0)';
                }
                startTimer(remainingTime);
            }
        };

        if (duration > 0) {
            startTimer(duration);
            toastEl.addEventListener('mouseenter', pauseTimer);
            toastEl.addEventListener('mouseleave', resumeTimer);
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                if (timeoutId) clearTimeout(timeoutId);
                dismiss();
            });
        }
    };

    // Initialize all existing server toasts
    if (toastContainer) {
        toastContainer.querySelectorAll('.custom-toast').forEach(initToast);
    }

    // Global helper to show client-side toasts
    window.showToast = (message, type = 'info', duration = 4000) => {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container-custom';
            container.setAttribute('aria-live', 'polite');
            container.setAttribute('aria-atomic', 'true');
            document.body.appendChild(container);
        }

        const icons = {
            success: 'bi-check-circle-fill text-success',
            error: 'bi-exclamation-octagon-fill text-danger',
            danger: 'bi-exclamation-octagon-fill text-danger',
            warning: 'bi-exclamation-triangle-fill text-warning',
            info: 'bi-info-circle-fill text-primary'
        };

        const toastEl = document.createElement('div');
        toastEl.className = `custom-toast toast-${type}`;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('data-auto-dismiss', duration);

        toastEl.innerHTML = `
            <div class="toast-icon">
                <i class="bi ${icons[type] || icons.info}"></i>
            </div>
            <div class="toast-body-content">
                <div class="toast-msg">${message}</div>
            </div>
            <button type="button" class="toast-close-btn" aria-label="Close">
                <i class="bi bi-x"></i>
            </button>
            <div class="toast-progress"></div>
        `;

        container.appendChild(toastEl);
        initToast(toastEl);
    };

});
