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
      
      navLinks.forEach(l => l.classList.remove('active'));
      pageContents.forEach(pc => pc.classList.remove('active'));
      
      link.classList.add('active');
      document.getElementById(`${pageName}-page`).classList.add('active');
      
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

  // ONLY ONE renderParkingLot function - DELETED THE DUPLICATE
 // Replace the renderParkingLot function with this optimized version

function renderParkingLot(slots) {
  if (!Array.isArray(slots) || slots.length === 0) {
    parkingLot.innerHTML = `
      <p style="color: #ef4444; text-align: center; padding: 60px 40px; font-size: 1.1em; font-weight: 600;">
        ⚠️ No parking slots available<br>
        <small style="color: #94a3b8; font-size: 0.9em;">Please check if Flask server is running and database is initialized</small>
      </p>
    `;
    updateStats([]);
    return;
  }

  parkingLot.innerHTML = '';
  
  // Create parking slots directly with optimized grid
  slots.forEach(slot => {
    const slotEl = document.createElement('div');
    slotEl.className = 'parking-slot ' + (slot.status === 'occupied' ? 'occupied' : 'available');
    
    const isOccupied = slot.status === 'occupied';
    const carIcon = isOccupied ? '<div class="car-icon">🚗</div>' : '';
    const plateInfo = isOccupied && slot.plate ? `<div class="slot-plate">${slot.plate}</div>` : '';
    
    slotEl.innerHTML = `
      <div class="slot-number">P${String(slot.number).padStart(2, '0')}</div>
      ${carIcon}
      ${plateInfo}
    `;
    
    // Add hover tooltip
    slotEl.title = `Slot ${slot.number} - ${isOccupied ? 'OCCUPIED' : 'AVAILABLE'}${isOccupied && slot.plate ? ` (${slot.plate})` : ''}`;
    
    parkingLot.appendChild(slotEl);
  });

  console.log('[SLOTS] Rendered ' + slots.length + ' slots');
  updateStats(slots);
}
  function loadSlots() {
    console.log('[SLOTS] Loading slots...');
    fetch('/api/slots')
      .then(r => {
        console.log('[SLOTS] Response status:', r.status);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        console.log('[SLOTS] Loaded:', data);
        if (!Array.isArray(data)) {
          throw new Error('Invalid slots data format');
        }
        if (data.length === 0) {
          console.warn('[SLOTS] WARNING: No slots returned from API!');
        }
        renderParkingLot(data);
      })
      .catch(err => {
        console.error('[SLOTS] Error:', err);
        showNotification('❌ Cannot load parking slots: ' + err.message, 'error');
      });
  }

  function loadVehicleDetails() {
    console.log('[DETAILS] Loading vehicle details...');
    fetch('/api/vehicle-details')
      .then(r => r.json())
      .then(data => {
        console.log('[DETAILS] Loaded:', data);
        renderVehicleDetails(data);
      })
      .catch(err => {
        console.error('[DETAILS] Error:', err);
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
            <th>Payment Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
    `;

    vehicles.forEach(vehicle => {
      const statusClass = vehicle.status === 'PARKED' ? 'status-parked' : 'status-exited';
      const paymentClass = vehicle.payment_status === 'paid' ? 'payment-paid' : 'payment-pending';
      const paymentText = vehicle.payment_status === 'paid' ? '✓ PAID' : '⏳ PENDING';
      
      let actionButtons = '';
      
      if (vehicle.payment_status === 'pending' && vehicle.time_out !== 'Still Parked') {
        const chargeAmount = parseFloat(vehicle.charge.replace('₹', ''));
        actionButtons = `
          <div class="action-buttons-group">
            <button class="btn-pay-slip" onclick="printPaymentSlip(${vehicle.id}, '${vehicle.plate}', '${vehicle.slot_number}', '${vehicle.time_in}', '${vehicle.time_out}', ${vehicle.duration_minutes}, '${vehicle.charge.replace('₹', '')}')">
              🖨️ View Slip
            </button>
            <button class="btn-verify" onclick="openPinModal(${vehicle.id}, '${vehicle.plate}', ${chargeAmount})">
              ✓ Verify
            </button>
          </div>
        `;
      } else if (vehicle.payment_status === 'paid') {
        actionButtons = '<span style="color: #10b981; font-weight: 600;">✓ Completed</span>';
      } else {
        actionButtons = '<span style="color: #6b7280;">Still Parked</span>';
      }

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
          <td>${actionButtons}</td>
        </tr>
      `;
    });

    html += `
        </tbody>
      </table>
    `;

    container.innerHTML = html;
  }

  // NEW: Generate random 6-digit PIN
  function generatePin() {
    return Math.floor(100000 + Math.random() * 900000).toString();
  }

  // MODIFIED: Print Payment Slip with PIN in QR Code
  function printPaymentSlip(txnId, plate, slotNumber, entryTime, exitTime, duration, charge) {
    const pin = generatePin();
    sessionStorage.setItem(`pin_${txnId}`, pin);
    
    const pinData = `PARKING_PIN|${pin}|${plate}|₹${charge}|TXN${txnId}`;
    const qrCodeUrl = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(pinData)}`;
    
    const printWindow = window.open('', '_blank', 'width=500,height=900');
    
    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <title>Payment Slip - ${plate}</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body { font-family: 'Arial', sans-serif; background: white; padding: 15px; color: #333; }
          .slip-container { max-width: 400px; margin: 0 auto; background: white; border: 2px solid #667eea; border-radius: 12px; padding: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
          .slip-header { text-align: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 3px dashed #667eea; }
          .slip-header h1 { font-size: 28px; color: #667eea; margin-bottom: 5px; }
          .slip-header p { font-size: 11px; color: #6b7280; }
          .slip-body { margin-bottom: 20px; }
          .slip-row { display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 13px; padding: 8px 0; }
          .slip-label { font-weight: 700; color: #1f2937; }
          .slip-value { text-align: right; color: #4b5563; font-family: 'Courier New', monospace; font-weight: 600; }
          .slip-divider { border-top: 2px dashed #e5e7eb; margin: 12px 0; }
          .slip-row.highlight { background: #f0f4ff; padding: 12px; border-radius: 6px; border-left: 4px solid #667eea; }
          .slip-row.highlight .slip-label { color: #667eea; font-size: 15px; }
          .slip-row.highlight .slip-value { color: #667eea; font-size: 18px; }
          .qr-section { text-align: center; margin: 20px 0; padding: 20px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb; }
          .qr-section h3 { font-size: 13px; color: #1f2937; margin-bottom: 12px; font-weight: 700; }
          .qr-section img { max-width: 200px; height: auto; border: 2px solid #667eea; border-radius: 6px; padding: 5px; background: white; }
          .qr-info { font-size: 11px; color: #6b7280; margin-top: 10px; line-height: 1.5; }
          .pin-display-section { background: #fef3c7; border: 2px solid #f59e0b; border-radius: 8px; padding: 15px; margin: 15px 0; text-align: center; }
          .pin-label { font-size: 11px; color: #92400e; font-weight: 700; margin-bottom: 8px; }
          .pin-number { font-size: 32px; font-weight: 900; color: #d97706; font-family: 'Courier New', monospace; letter-spacing: 4px; background: white; padding: 12px; border-radius: 6px; border: 2px solid #f59e0b; }
          .slip-footer { text-align: center; font-size: 11px; color: #6b7280; border-top: 2px dashed #e5e7eb; padding-top: 12px; margin-top: 12px; }
          .slip-footer p { margin-bottom: 6px; }
          .thank-you { font-size: 13px; font-weight: 700; color: #667eea; margin-bottom: 8px; }
          .action-buttons { display: flex; gap: 8px; margin-top: 12px; }
          .action-btn { flex: 1; padding: 10px; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.3s; }
          .print-btn { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
          .print-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }
          .close-btn { background: #e5e7eb; color: #1f2937; }
          .close-btn:hover { background: #d1d5db; }
          @media print { body { padding: 0; } .slip-container { box-shadow: none; border: 1px solid #ccc; } .action-buttons { display: none; } }
        </style>
      </head>
      <body>
        <div class="slip-container">
          <div class="slip-header">
            <h1>🅿️ SMART PARKING</h1>
            <p>Payment Receipt & Invoice</p>
          </div>
          
          <div class="slip-body">
            <div class="slip-row">
              <span class="slip-label">License Plate:</span>
              <span class="slip-value">${plate}</span>
            </div>
            <div class="slip-row">
              <span class="slip-label">Parking Slot:</span>
              <span class="slip-value">P${String(slotNumber).padStart(2, '0')}</span>
            </div>
            <div class="slip-divider"></div>
            <div class="slip-row">
              <span class="slip-label">Entry Time:</span>
              <span class="slip-value">${entryTime}</span>
            </div>
            <div class="slip-row">
              <span class="slip-label">Exit Time:</span>
              <span class="slip-value">${exitTime}</span>
            </div>
            <div class="slip-row">
              <span class="slip-label">Duration:</span>
              <span class="slip-value">${duration} min</span>
            </div>
            <div class="slip-divider"></div>
            <div class="slip-row">
              <span class="slip-label">Rate:</span>
              <span class="slip-value">₹5/min</span>
            </div>
            <div class="slip-row">
              <span class="slip-label">Calculation:</span>
              <span class="slip-value">${duration} × ₹5</span>
            </div>
            <div class="slip-row highlight">
              <span class="slip-label">AMOUNT DUE:</span>
              <span class="slip-value">₹${charge}</span>
            </div>
          </div>
          
          <div class="qr-section">
            <h3>📱 Scan to Get PIN</h3>
            <img src="${qrCodeUrl}" alt="Payment QR Code">
            <div class="qr-info">✓ QR contains your PIN<br>✓ Also shows on this slip<br>✓ Use PIN to verify payment</div>
          </div>
          
          <div class="slip-footer">
            <p class="thank-you">Thank You! 🙏</p>
            <p>For using Smart Parking System</p>
            <p style="margin-top: 8px; font-size: 10px;">Transaction ID: TXN${txnId}<br>Generated: ${new Date().toLocaleString()}<br>Valid for 24 hours</p>
          </div>
          
          <div class="action-buttons">
            <button class="action-btn print-btn" onclick="window.print()">🖨️ Print Slip</button>
            <button class="action-btn close-btn" onclick="window.close()">✕ Close</button>
          </div>
        </div>
      </body>
      </html>
    `;
    
    printWindow.document.write(htmlContent);
    printWindow.document.close();
  }

  window.printPaymentSlip = printPaymentSlip;

  // NEW: Open PIN verification modal
  function openPinModal(txnId, plate, amount) {
    window.currentTxnId = txnId;
    window.currentPlate = plate;
    window.currentAmount = amount;
    
    const modal = document.getElementById('pinModal');
    const pinInput = document.getElementById('pinInput');
    
    modal.style.display = 'flex';
    pinInput.value = '';
    pinInput.focus();
    
    const helperText = document.getElementById('pinHelperText');
    helperText.textContent = '';
    helperText.className = 'pin-helper-text';
  }

  function closePinModal() {
    const modal = document.getElementById('pinModal');
    modal.style.display = 'none';
    window.currentTxnId = null;
    window.currentPlate = null;
    window.currentAmount = null;
  }

  function verifyPin() {
    const pinInput = document.getElementById('pinInput');
    const enteredPin = pinInput.value.trim();
    const helperText = document.getElementById('pinHelperText');
    
    if (!enteredPin || enteredPin.length !== 6 || !/^\d{6}$/.test(enteredPin)) {
      helperText.textContent = '❌ Please enter a valid 6-digit PIN';
      helperText.className = 'pin-helper-text error';
      pinInput.style.borderColor = '#ef4444';
      return;
    }
    
    const storedPin = sessionStorage.getItem(`pin_${window.currentTxnId}`);
    
    if (!storedPin) {
      helperText.textContent = '❌ PIN not found. Please try again.';
      helperText.className = 'pin-helper-text error';
      pinInput.style.borderColor = '#ef4444';
      return;
    }
    
    if (enteredPin === storedPin) {
      helperText.textContent = '✓ PIN verified! Processing payment...';
      helperText.className = 'pin-helper-text success';
      pinInput.style.borderColor = '#10b981';
      
      setTimeout(() => {
        processPaymentAfterPin();
      }, 1000);
    } else {
      helperText.textContent = '❌ Incorrect PIN. Please try again.';
      helperText.className = 'pin-helper-text error';
      pinInput.style.borderColor = '#ef4444';
      pinInput.value = '';
      pinInput.focus();
    }
  }

  function processPaymentAfterPin() {
    const txnId = window.currentTxnId;
    const plate = window.currentPlate;
    const amount = window.currentAmount;
    
    if (!txnId) return;
    
    fetch(`/api/payment/process/${txnId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin_verified: true })
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showNotification(`✓ Payment successful for ${plate}!`, 'success');
        closePinModal();
        loadVehicleDetails();
        sessionStorage.removeItem(`pin_${txnId}`);
      } else {
        showNotification(`✗ Payment failed: ${data.error}`, 'error');
      }
    })
    .catch(err => {
      showNotification(`✗ Error: ${err}`, 'error');
    });
  }

  window.openPinModal = openPinModal;
  window.closePinModal = closePinModal;
  window.verifyPin = verifyPin;

  entryForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const plate = entryForm.plate.value.trim().toUpperCase();
    
    if (!plate) {
      showNotification('❌ Please enter a plate number', 'error');
      return;
    }
    
    console.log('[ENTRY] Submitting:', plate);
    const res = await postPlate('/api/entry', plate);
    console.log('[ENTRY] Response:', res);
    
    if (res.success) {
      entryForm.reset();
      loadSlots();
      loadVehicleDetails();
      showNotification('✓ Vehicle entered: ' + plate + ' → Slot ' + res.slot_number, 'success');
    } else {
      showNotification('✗ Entry failed: ' + (res.error || 'Unknown error'), 'error');
    }
  });

  exitForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const plate = exitForm.plate.value.trim().toUpperCase();
    
    if (!plate) {
      showNotification('❌ Please enter a plate number', 'error');
      return;
    }
    
    console.log('[EXIT] Submitting:', plate);
    const res = await postPlate('/api/exit', plate);
    console.log('[EXIT] Response:', res);
    
    if (res.success) {
      exitForm.reset();
      loadSlots();
      loadVehicleDetails();
      const charge = res.charge ? ' (Charge: ₹' + res.charge + ')' : '';
      showNotification('✓ Vehicle exited: ' + plate + charge, 'success');
    } else {
      showNotification('✗ Exit failed: ' + (res.error || 'Unknown error'), 'error');
    }
  });

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

  // IMPORTANT: Load slots on page load
  console.log('[INIT] Page loaded, calling loadSlots()');
  loadSlots();

  // Refresh every 5 seconds
  setInterval(loadSlots, 5000);
});