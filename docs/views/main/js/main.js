/**
 * Main Application Entry Point — Monocular Spatial Vision Portal
 * Specification: docs/views/main/design-system.md
 */

function initApp() {
  if (window.Navigation) {
    window.Navigation.init();
  }
}

// Ensure execution even if DOMContentLoaded already fired
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}
