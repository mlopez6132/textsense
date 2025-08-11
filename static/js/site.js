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


