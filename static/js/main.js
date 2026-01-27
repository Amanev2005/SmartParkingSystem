document.addEventListener('DOMContentLoaded', () => {
  const entryForm = document.getElementById('entryForm');
  const exitForm = document.getElementById('exitForm');
  const parkingLot = document.getElementById('parkingLot');
  const navLinks = document.querySelectorAll('.nav-link');
  const pageContents = document.querySelectorAll('.page-content');

  // Navigation functionality
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const pageName = link.dataset.page;
      
      // Remove active class from all links and pages
      navLinks.forEach(l => l.classList.remove('active'));
      pageContents.forEach(pc => pc.classList.remove('active'));
      
      // Add active class to clicked link and corresponding page
      link.classList.add('active');
      document.getElementById(`${pageName}-page`).classList.add('active');
      
      // Load details when details page is opened
      if (pageName === 'details') {
        loadVehicleDetails();
      }
    });
  });

  function postPlate(url, plate) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ plate })
    }).then(r => r.json()).catch(err => ({ success: false, error: String(err) }));
  }

  function updateStats(slots) {
    const available = slots.filter(s => s.status !== 'occupied').length;
    const occupied = slots.filter(s => s.status === 'occupied').length;
    const total = slots.length;

    document.getElementById('availableCount').textContent = available;
    document.getElementById('occupiedCount').textContent = occupied;
    document.getElementById('totalCount').textContent = total;
  }

  function renderParkingLot(slots) {
    if (!Array.isArray(slots) || slots.length === 0) {
      parkingLot.innerHTML = '<p style="color: #9ca3af; text-align: center;">No parking slots available</p>';
      return;
    }

    parkingLot.innerHTML = '';
    
    // Group slots into rows of 4
    const slotsPerRow = 4;
    for (let i = 0; i < slots.length; i += slotsPerRow) {
      const rowSlots = slots.slice(i, i + slotsPerRow);
      
      rowSlots.forEach(slot => {
        const slotEl = document.createElement('div');
        slotEl.className = 'parking-slot ' + (slot.status === 'occupied' ? 'occupied' : 'available');
        
        const isOccupied = slot.status === 'occupied';
        const carIcon = isOccupied ? '🚗' : '';
        const plateInfo = isOccupied && slot.plate ? `<div class="slot-plate">${slot.plate}</div>` : '';
        
        slotEl.innerHTML = `
          <div class="slot-number">P${String(slot.number).padStart(2, '0')}</div>
          ${carIcon ? `<div class="car-icon">${carIcon}</div>` : ''}
          ${plateInfo}
        `;
        
        parkingLot.appendChild(slotEl);
      });
    }

    updateStats(slots);
  }

  function loadSlots() {
    fetch('/api/slots')
      .then(r => r.json())
      .then(data => {
        renderParkingLot(data);
      })
      .catch(() => {
        const demoSlots = Array.from({length: 12}, (_, i) => ({
          number: i + 1,
          status: Math.random() > 0.6 ? 'occupied' : 'available',
          plate: Math.random() > 0.6 ? `KA${String(Math.floor(Math.random() * 100)).padStart(2, '0')}AB${Math.floor(1000 + Math.random() * 9000)}` : null
        }));
        renderParkingLot(demoSlots);
      });
  }

  function loadVehicleDetails() {
    fetch('/api/vehicle-details')
      .then(r => r.json())
      .then(data => {
        renderVehicleDetails(data);
      })
      .catch(err => {
        document.getElementById('detailsContainer').innerHTML = `<p style="color: #ef4444; text-align: center;">Error loading details: ${err}</p>`;
      });
  }

  function renderVehicleDetails(vehicles) {
    const container = document.getElementById('detailsContainer');
    
    if (!Array.isArray(vehicles) || vehicles.length === 0) {
      container.innerHTML = '<p style="color: #9ca3af; text-align: center;">No vehicle records found</p>';
      return;
    }

    let html = `
      <table class="details-table">
        <thead>
          <tr>
            <th>Slot No.</th>
            <th>License Plate</th>
            <th>Entry Time</th>
            <th>Exit Time</th>
            <th>Duration (min)</th>
            <th>Charge</th>
            <th>Status</th>
            <th>Payment</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
    `;

    vehicles.forEach(vehicle => {
      const statusClass = vehicle.status === 'PARKED' ? 'status-parked' : 'status-exited';
      const paymentClass = vehicle.payment_status === 'paid' ? 'payment-paid' : 'payment-pending';
      const paymentText = vehicle.payment_status === 'paid' ? '✓ PAID' : '⏳ PENDING';
      
      const actionBtn = vehicle.payment_status === 'pending' && vehicle.time_out !== 'Still Parked' ? 
        `<button class="pay-btn" onclick="processPayment(${vehicle.id}, '${vehicle.plate}', ${vehicle.charge.replace('₹', '')})">💳 Pay Now</button>` : 
        '<span style="color: #10b981;">✓ Completed</span>';

      html += `
        <tr>
          <td><strong>${vehicle.slot_number}</strong></td>
          <td><span class="plate-badge">${vehicle.plate}</span></td>
          <td>${vehicle.time_in}</td>
          <td>${vehicle.time_out}</td>
          <td>${vehicle.duration_minutes}</td>
          <td><strong>${vehicle.charge}</strong></td>
          <td><span class="status-badge ${statusClass}">${vehicle.status}</span></td>
          <td><span class="payment-badge ${paymentClass}">${paymentText}</span></td>
          <td>${actionBtn}</td>
        </tr>
      `;
    });

    html += `
        </tbody>
      </table>
    `;

    container.innerHTML = html;
  }

  function processPayment(txnId, plate, amount) {
    if (confirm(`Process payment of ₹${amount.toFixed(2)} for vehicle ${plate}?`)) {
      fetch(`/api/payment/process/${txnId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      .then(r => r.json())
      .then(data => {
        if (data.success) {
          showNotification(`✓ Payment successful for ${plate}`, 'success');
          loadVehicleDetails();
        } else {
          showNotification(`✗ Payment failed: ${data.error}`, 'error');
        }
      })
      .catch(err => {
        showNotification(`✗ Error: ${err}`, 'error');
      });
    }
  }

  // Expose processPayment to global scope for onclick handlers
  window.processPayment = processPayment;

  entryForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const plate = entryForm.plate.value.trim().toUpperCase();
    if (!plate) return;
    
    const res = await postPlate('/api/entry', plate);
    console.log('entry response', res);
    
    if (res.success) {
      entryForm.reset();
      loadSlots();
      showNotification('✓ Vehicle entered: ' + plate, 'success');
    } else {
      showNotification('✗ Entry failed: ' + (res.error || 'Unknown error'), 'error');
    }
  });

  exitForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const plate = exitForm.plate.value.trim().toUpperCase();
    if (!plate) return;
    
    const res = await postPlate('/api/exit', plate);
    console.log('exit response', res);
    
    if (res.success) {
      exitForm.reset();
      loadSlots();
      showNotification('✓ Vehicle exited: ' + plate + ` (Charge: ${res.charge}₹)`, 'success');
    } else {
      showNotification('✗ Exit failed: ' + (res.error || 'Unknown error'), 'error');
    }
  });

  // Refresh button for details page
  const refreshBtn = document.getElementById('refreshDetailsBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', loadVehicleDetails);
  }

  function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: ${type === 'success' ? '#10b981' : '#ef4444'};
      color: white;
      padding: 16px 24px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      z-index: 1000;
      font-weight: 600;
      animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  // Add animations
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn {
      from { transform: translateX(400px); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
      from { transform: translateX(0); opacity: 1; }
      to { transform: translateX(400px); opacity: 0; }
    }
  `;
  document.head.appendChild(style);

  // Initial load
  loadSlots();

  // Refresh every 5 seconds
  setInterval(loadSlots, 5000);
});