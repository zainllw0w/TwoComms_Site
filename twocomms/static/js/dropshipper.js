(() => {
  document.addEventListener('DOMContentLoaded', () => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    setupTabNavigation();
    setupScrollLinks();
    setupAutoAnimateSections();

    function setupTabNavigation() {
      const tabLinks = document.querySelectorAll('[data-tab-target]');
      const tabPanels = document.querySelectorAll('[data-tab-panel]');

      if (!tabLinks.length || !tabPanels.length) {
        return;
      }

      tabLinks.forEach((link) => {
        link.addEventListener('click', (event) => {
          const target = event.currentTarget.getAttribute('data-tab-target');
          if (!target) {
            return;
          }

          const targetPanel = document.querySelector(`[data-tab-panel="${target}"]`);
          if (!targetPanel) {
            return;
          }

          event.preventDefault();
          event.currentTarget.classList.add('is-active');

          tabLinks.forEach((other) => {
            if (other !== event.currentTarget) {
              other.classList.remove('is-active');
            }
          });

          tabPanels.forEach((panel) => {
            panel.classList.toggle('is-active', panel === targetPanel);
          });

          if (targetPanel.dataset.tabAutoload && !targetPanel.dataset.tabLoaded) {
            fetch(targetPanel.dataset.tabAutoload)
              .then((response) => response.text())
              .then((html) => {
                targetPanel.innerHTML = html;
                targetPanel.dataset.tabLoaded = 'true';
              })
              .catch((error) => {
                console.error('Не вдалося завантажити дані вкладки:', error);
              });
          }
        });
      });
    }

    function setupScrollLinks() {
      const scrollLinks = document.querySelectorAll('[data-scroll-target]');
      if (!scrollLinks.length) {
        return;
      }

      scrollLinks.forEach((link) => {
        link.addEventListener('click', (event) => {
          const targetId = link.getAttribute('data-scroll-target');
          const target = document.getElementById(targetId);
          if (!target) {
            return;
          }

          event.preventDefault();
          target.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'start' });
        });
      });
    }

    function setupAutoAnimateSections() {
      if (prefersReducedMotion) {
        return;
      }

      const animatedBlocks = document.querySelectorAll('[data-animate]');
      if (!animatedBlocks.length) {
        return;
      }

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('is-animated');
              observer.unobserve(entry.target);
            }
          });
        },
        {
          threshold: 0.2,
          rootMargin: '0px 0px -15% 0px',
        },
      );

      animatedBlocks.forEach((block) => observer.observe(block));
    }
  });
})();
