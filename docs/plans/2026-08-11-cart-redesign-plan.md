# Cart Redesign Implementation Plan

Goal: Ship a mobile-first cart card system that preserves cart behavior and renders cleanly at every supported viewport.

Architecture: Keep pages/cart.html data and JavaScript contracts intact. Add accessible action spans and labels in the template and let cart-items-redesign.css, loaded last, own the cart header, item cards, and responsive behavior.

Tech Stack: Django templates, CSS grid and flex, existing vanilla JavaScript, Django TestCase, Playwright CLI, SSH deployment.

## Tasks

1. Add the regression contract in twocomms/storefront/tests/test_cart.py for no header clipping, wrapped mobile metadata, mobile grid areas, and the desktop breakpoint.
2. Keep accessible cart actions in twocomms/twocomms_django_theme/templates/pages/cart.html by wrapping action text in cart-action-label, adding aria labels, and preserving all data attributes.
3. Own the responsive visual layer in twocomms/twocomms_django_theme/static/css/cart-items-redesign.css and synchronize API-rendered rows in twocomms/twocomms_django_theme/static/js/modules/cart.js.
4. Run focused checks, browser viewport measurements, git diff check, then commit only the cart files and plans, push main, pull on the supplied server, run collectstatic and restart, and smoke-test cart and the deployed static asset.
