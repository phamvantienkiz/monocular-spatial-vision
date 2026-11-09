/**
 * Navigation & Interactive Listeners — Soft Clean Cards
 * Specification: docs/views/main/design-system.md
 */

const Navigation = {
  init: function() {
    this.setupSmoothScroll();
    this.setupScrollSpy();
    this.setupSegmentedTabs();
    this.setupAcademicTabs();
    this.setupModalDismiss();
  },

  setupSmoothScroll: function() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        const targetId = this.getAttribute('href');
        if (targetId === '#' || !targetId.startsWith('#')) return;

        const targetEl = document.querySelector(targetId);
        if (targetEl) {
          e.preventDefault();
          const headerOffset = 70;
          const elementPosition = targetEl.getBoundingClientRect().top;
          const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

          window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
          });
        }
      });
    });
  },

  setupScrollSpy: function() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link');

    window.addEventListener('scroll', () => {
      let currentSection = '';
      const scrollPos = window.pageYOffset + 120;

      sections.forEach(sec => {
        const top = sec.offsetTop;
        const height = sec.offsetHeight;
        if (scrollPos >= top && scrollPos < top + height) {
          currentSection = sec.getAttribute('id');
        }
      });

      navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${currentSection}`) {
          link.classList.add('active');
        }
      });
    }, { passive: true });
  },

  setupSegmentedTabs: function() {
    const tabContainer = document.getElementById('solution-filter-tabs');
    if (!tabContainer) return;

    tabContainer.querySelectorAll('.segmented-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        tabContainer.querySelectorAll('.segmented-btn').forEach(b => {
          b.setAttribute('aria-selected', 'false');
          b.classList.remove('active');
        });

        this.setAttribute('aria-selected', 'true');
        this.classList.add('active');

        const category = this.getAttribute('data-filter') || 'all';
        Navigation.filterSolutions(category);
      });
    });
  },

  filterSolutions: function(category) {
    const container = document.getElementById('solutions-container');
    if (!container) return;

    const blocks = container.querySelectorAll('.module-block');
    blocks.forEach(block => {
      const blockCat = block.getAttribute('data-category');
      if (category === 'all' || blockCat === category) {
        block.style.display = 'flex';
      } else {
        block.style.display = 'none';
      }
    });
  },

  setupAcademicTabs: function() {
    const tabContainer = document.getElementById('academic-benchmark-tabs');
    if (!tabContainer) return;

    tabContainer.querySelectorAll('.segmented-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        tabContainer.querySelectorAll('.segmented-btn').forEach(b => {
          b.setAttribute('aria-selected', 'false');
          b.classList.remove('active');
        });

        this.setAttribute('aria-selected', 'true');
        this.classList.add('active');

        const tabTarget = this.getAttribute('data-bench-tab') || 'all';
        const section = document.getElementById('academic-benchmarks');
        if (!section) return;

        const panels = section.querySelectorAll('.benchmark-panel');
        panels.forEach(p => {
          if (tabTarget === 'all' || p.getAttribute('data-panel') === tabTarget) {
            p.classList.add('active');
          } else {
            p.classList.remove('active');
          }
        });
      });
    });
  },

  setupModalDismiss: function() {
    const overlay = document.getElementById('modal-overlay');
    if (!overlay) return;

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        UIComponents.closeModal();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        UIComponents.closeModal();
      }
    });
  }
};

window.Navigation = Navigation;
