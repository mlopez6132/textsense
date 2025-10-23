// Site-wide utilities: Cookie consent banner and small helpers

(function () {
  try {
    // Cookie consent banner
    var CONSENT_KEY = 'cookieConsent';
    function hasConsent() {
      try { return localStorage.getItem(CONSENT_KEY) === 'accepted'; } catch (e) { return false; }
    }
    function setConsent() {
      try { localStorage.setItem(CONSENT_KEY, 'accepted'); } catch (e) {}
      var bar = document.getElementById('cookie-consent-banner');
      if (bar) bar.remove();
      document.dispatchEvent(new CustomEvent('cookie-consent-accepted'));
    }

    function injectStyles() {
      var css = '\n#cookie-consent-banner{position:fixed;left:16px;right:16px;bottom:16px;z-index:99999;background:#0f172a;color:#fff;border-radius:12px;padding:14px 16px;box-shadow:0 10px 30px rgba(2,6,23,.25)}\n#cookie-consent-banner .cc-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}\n#cookie-consent-banner a{color:#93c5fd;text-decoration:underline}\n#cookie-consent-banner button{border:none;border-radius:8px;padding:8px 14px;font-weight:600;cursor:pointer}\n#cookie-consent-banner .cc-accept{background:#22c55e;color:#052e12}\n#cookie-consent-banner .cc-decline{background:#334155;color:#e2e8f0}\n';
      var style = document.createElement('style');
      style.textContent = css; document.head.appendChild(style);
    }

    function renderBanner() {
      if (hasConsent()) return;
      injectStyles();
      var bar = document.createElement('div');
      bar.id = 'cookie-consent-banner';
      bar.innerHTML = ''+
        '<div class="cc-body">'+
          '<div>We use cookies to improve your experience and for analytics. See our <a href="/privacy">Privacy Policy</a> and <a href="/cookies">Cookies</a>.</div>'+
          '<div class="cc-actions">'+
            '<button class="cc-accept">Accept</button>'+
            '<button class="cc-decline" type="button">Decline</button>'+
          '</div>'+
        '</div>';
      document.body.appendChild(bar);
      bar.querySelector('.cc-accept').addEventListener('click', setConsent);
      bar.querySelector('.cc-decline').addEventListener('click', function(){ bar.remove(); });
    }

    if (document.readyState === 'complete' || document.readyState === 'interactive') {
      setTimeout(renderBanner, 0);
    } else {
      document.addEventListener('DOMContentLoaded', renderBanner);
    }
  } catch (e) {
    // no-op
  }
})();


// Keep HF Spaces warm by pinging periodically
(function () {
  try {
    var SPACES = [
      'https://mlopez6132-textsense-inference.hf.space/healthz',
      'https://mlopez6132-textsense-audio-text.hf.space/healthz',
      'https://mlopez6132-textsense-ocr.hf.space/healthz'
    ];
    var RELAY = '/ping';

    function pingAll() {
      try {
        // Ping local relay first (very fast)
        fetch(RELAY, { method: 'GET', cache: 'no-store' }).catch(function () {});
        // Ping each space health endpoint
        for (var i = 0; i < SPACES.length; i++) {
          fetch(SPACES[i], { method: 'GET', cache: 'no-store', mode: 'no-cors' }).catch(function () {});
        }
      } catch (e) {}
    }

    if (document.readyState === 'complete' || document.readyState === 'interactive') {
      pingAll();
    } else {
      document.addEventListener('DOMContentLoaded', pingAll);
    }
    // every 5 minutes
    setInterval(pingAll, 5 * 60 * 1000);
  } catch (e) {}
})();

// Accessible mobile nav toggle for header
(function () {
  'use strict';
  
  // Wait for DOM to be ready
  document.addEventListener('DOMContentLoaded', function() {
    const menuToggle = document.querySelector('.menu-toggle');
    const siteNav = document.querySelector('.site-nav');
    
    if (!menuToggle || !siteNav) {
      console.warn('Header elements not found');
      return;
    }
    
    // State management
    let isMenuOpen = false;
    
    /**
     * Toggle mobile menu visibility and ARIA states
     */
    function toggleMenu() {
      isMenuOpen = !isMenuOpen;
      
      // Update ARIA attributes
      menuToggle.setAttribute('aria-expanded', isMenuOpen.toString());
      siteNav.setAttribute('aria-expanded', isMenuOpen.toString());
      
      // Update button label for screen readers
      menuToggle.setAttribute('aria-label', 
        isMenuOpen ? 'Close navigation menu' : 'Open navigation menu'
      );
      
      // Prevent body scroll when menu is open (mobile only)
      if (window.innerWidth <= 768) {
        document.body.style.overflow = isMenuOpen ? 'hidden' : '';
      }
    }
    
    /**
     * Close menu and reset states
     */
    function closeMenu() {
      if (isMenuOpen) {
        isMenuOpen = false;
        menuToggle.setAttribute('aria-expanded', 'false');
        siteNav.setAttribute('aria-expanded', 'false');
        menuToggle.setAttribute('aria-label', 'Open navigation menu');
        document.body.style.overflow = '';
      }
    }
    
    /**
     * Handle menu toggle button click
     */
    menuToggle.addEventListener('click', function(e) {
      e.preventDefault();
      toggleMenu();
    });
    
    /**
     * Handle escape key to close menu
     */
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && isMenuOpen) {
        closeMenu();
        menuToggle.focus(); // Return focus to toggle button
      }
    });
    
    /**
     * Handle clicks outside menu to close it
     */
    document.addEventListener('click', function(e) {
      if (isMenuOpen && 
          !siteNav.contains(e.target) && 
          !menuToggle.contains(e.target)) {
        closeMenu();
      }
    });
    
    /**
     * Handle window resize - close menu on desktop
     */
    window.addEventListener('resize', function() {
      if (window.innerWidth > 768 && isMenuOpen) {
        closeMenu();
      }
    });
    
    /**
     * Handle navigation link clicks - close menu on mobile
     */
    const navLinks = siteNav.querySelectorAll('.nav-link');
    navLinks.forEach(function(link) {
      link.addEventListener('click', function() {
        if (window.innerWidth <= 768) {
          closeMenu();
        }
      });
    });
    
    /**
     * Initialize ARIA states
     */
    function initializeAriaStates() {
      menuToggle.setAttribute('aria-expanded', 'false');
      siteNav.setAttribute('aria-expanded', 'false');
      menuToggle.setAttribute('aria-label', 'Open navigation menu');
    }
    
    // Initialize on load
    initializeAriaStates();
    
    // Expose utility functions for external use
    window.TextSenseHeader = {
      toggleMenu: toggleMenu,
      closeMenu: closeMenu,
      isMenuOpen: function() { return isMenuOpen; }
    };
  });
})();

