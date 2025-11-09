// Minimal client behavior to avoid console errors and allow manual testing.
document.addEventListener('DOMContentLoaded', () => {
  const entryForm = document.getElementById('entryForm');
  const exitForm = document.getElementById('exitForm');

  function postPlate(url, plate) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ plate })
    }).then(r => r.json()).catch(err => ({ success: false, error: String(err) }));
  }

  entryForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const plate = entryForm.plate.value.trim();
    if (!plate) return;
    const res = await postPlate('/api/entry', plate);
    console.log('entry response', res);
  });

  exitForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const plate = exitForm.plate.value.trim();
    if (!plate) return;
    const res = await postPlate('/api/exit', plate);
    console.log('exit response', res);
  });

  // Optionally populate slots if API exists
  fetch('/api/slots').then(r => r.json()).then(data => {
    if (!Array.isArray(data)) return;
    const grid = document.getElementById('slotGrid');
    grid.innerHTML = '';
    data.forEach(s => {
      const el = document.createElement('div');
      el.className = 'slot' + (s.status === 'occupied' ? ' occupied' : '');
      el.textContent = `#${s.number} — ${s.status}`;
      grid.appendChild(el);
    });
  }).catch(()=>{ /* ignore if endpoint absent */ });
});