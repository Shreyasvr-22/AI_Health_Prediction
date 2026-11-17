document.addEventListener('DOMContentLoaded', () => {
  const dobInput = document.getElementById('dob');
  if (dobInput) {
    dobInput.addEventListener('input', function () {
      let digits = this.value.replace(/\D/g, '').slice(0, 8);

      if (digits.length > 4) {
        digits = digits.slice(0, 2) + '/' +
                 digits.slice(2, 4) + '/' +
                 digits.slice(4);
      } else if (digits.length > 2) {
        digits = digits.slice(0, 2) + '/' +
                 digits.slice(2);
      }

      this.value = digits;
    });
  }

  document.querySelectorAll('.flash-close').forEach((button) => {
    button.addEventListener('click', () => button.closest('.flash')?.remove());
  });

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const message = form.getAttribute('data-confirm') || 'Are you sure?';
      if (!window.confirm(message)) event.preventDefault();
    });
  });

  // Prevent accidental whitespace-only submissions; server-side validation remains authoritative.
  document.querySelectorAll('form.patient-form, form.patient-form-inline').forEach((form) => {
    form.addEventListener('submit', () => {
      form.querySelectorAll('input[type="text"], input[type="email"]').forEach((input) => {
        input.value = input.value.trim();
      });
    });
  });
});
