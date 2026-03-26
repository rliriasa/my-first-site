(function () {
  // Active nav link
  var page = window.location.pathname.split('/').pop() || 'index.html';
  if (!page || page === '') page = 'index.html';
  var links = document.querySelectorAll('.nav-links a');
  links.forEach(function (a) {
    if (a.getAttribute('href') === page) {
      a.classList.add('nav-active');
    }
  });

  // Page entry transition
  var main = document.querySelector('body > div');
  if (main) {
    main.classList.add('page-enter');
  }

  // Hamburger menu
  var nav      = document.querySelector('nav');
  var navLinks = document.querySelector('.nav-links');
  if (nav && navLinks) {
    var btn = document.createElement('button');
    btn.className = 'ham-btn';
    btn.setAttribute('aria-label', 'Toggle menu');
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = '<span></span><span></span><span></span>';
    nav.appendChild(btn);

    function closeMenu() {
      navLinks.classList.remove('mob-open');
      btn.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
    function openMenu() {
      navLinks.classList.add('mob-open');
      btn.classList.add('open');
      btn.setAttribute('aria-expanded', 'true');
    }

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      navLinks.classList.contains('mob-open') ? closeMenu() : openMenu();
    });

    // Close on nav link click
    links.forEach(function (a) {
      a.addEventListener('click', closeMenu);
    });

    // Close when tapping outside
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target)) closeMenu();
    });
  }

  // Scroll reveal
  if ('IntersectionObserver' in window) {
    var revealEls = document.querySelectorAll('.sa, .mc, .ni, .sr, .fb, .ci, .scard, .role-card, .mets, .verdict, .pf-kpi, .alloc-card > div, .pub-item');
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.06, rootMargin: '0px 0px -40px 0px' });
    revealEls.forEach(function (el) {
      var rect = el.getBoundingClientRect();
      if (rect.top > window.innerHeight * 0.85) {
        el.classList.add('rv');
        io.observe(el);
      }
    });
  }
})();
