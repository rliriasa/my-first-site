(function () {
  // Set active nav link based on current page filename
  var page = window.location.pathname.split('/').pop() || 'index.html';
  if (!page || page === '') page = 'index.html';
  var links = document.querySelectorAll('.nav-links a');
  links.forEach(function (a) {
    if (a.getAttribute('href') === page) {
      a.classList.add('nav-active');
    }
  });

  // Page entry transition — animate the first non-nav block
  var main = document.querySelector('body > div');
  if (main) {
    main.classList.add('page-enter');
  }
})();
