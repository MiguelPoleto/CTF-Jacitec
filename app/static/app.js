(() => {
  function parseUtc(value) {
    if (!value) return null;
    const normalized = value.includes('T') ? value : value.replace(' ', 'T');
    const date = new Date(`${normalized}Z`);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const dateTimeFormatter = new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'medium'
  });

  document.querySelectorAll('[data-datetime]').forEach((element) => {
    const date = parseUtc(element.dataset.datetime);
    if (date) {
      element.textContent = dateTimeFormatter.format(date);
      element.setAttribute('datetime', date.toISOString());
    }
  });

  const currentDate = document.querySelector('[data-current-date]');
  if (currentDate) {
    currentDate.textContent = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'long' }).format(new Date());
  }
})();
