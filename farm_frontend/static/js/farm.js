// Stepper buttons: change the sibling number input and fire "input" so HTMX re-posts.
document.addEventListener('click', function (e) {
  var btn = e.target.closest('.step-btn');
  if (!btn) return;
  var input = btn.parentElement.querySelector('input');
  var step = parseInt(btn.dataset.step, 10) || 0;
  var min = input.min !== '' ? parseInt(input.min, 10) : 0;
  input.value = Math.max(min, (parseInt(input.value, 10) || 0) + step);
  input.dispatchEvent(new Event('input', { bubbles: true }));
});

// Toasts. Server sends:  HX-Trigger: {"toast": {"message": "...", "level": "success|danger|warning"}}
function showToast(message, level) {
  var box = document.getElementById('toasts');
  if (!box || !window.bootstrap) return;
  var color = { success: 'text-bg-success', danger: 'text-bg-danger', warning: 'text-bg-warning' }[level] || 'text-bg-success';
  var el = document.createElement('div');
  el.className = 'toast align-items-center border-0 ' + color;
  el.setAttribute('role', 'alert');
  el.innerHTML = '<div class="d-flex"><div class="toast-body"></div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
  el.querySelector('.toast-body').textContent = message;
  box.appendChild(el);
  var t = new bootstrap.Toast(el, { delay: 4000 });
  el.addEventListener('hidden.bs.toast', function () { el.remove(); });
  t.show();
}
document.addEventListener('toast', function (e) {
  var d = e.detail || {};
  showToast(d.message || d.value || 'Done', d.level || 'success');
});
document.body && document.body.addEventListener('htmx:responseError', function (e) {
  showToast('Something went wrong (' + e.detail.xhr.status + ')', 'danger');
});
document.addEventListener('htmx:responseError', function (e) {
  showToast('Something went wrong (' + e.detail.xhr.status + ')', 'danger');
});
