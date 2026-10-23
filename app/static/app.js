document.addEventListener('click', function (event) {
  var target = event.target.closest('[data-print]');
  if (target) { event.preventDefault(); window.print(); }
});
