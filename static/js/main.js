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

// ...existing code...

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

  // NEW: Print receipt function
  function printReceipt(txnId, plate, slotNumber, entryTime, exitTime, duration, charge) {
    // Create payment data string for QR code
    const paymentData = `PARKING|${plate}|${slotNumber}|₹${charge}|${new Date().toISOString()}`;
    
    // Open print window
    const printWindow = window.open('', '_blank', 'width=500,height=700');
    
    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <title>Parking Receipt - ${plate}</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
          * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
          }
          
          body {
            font-family: 'Arial', sans-serif;
            background: white;
            padding: 20px;
            color: #333;
          }
          
          .receipt-container {
            max-width: 400px;
            margin: 0 auto;
            background: white;
            border: 2px solid #667eea;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
          }
          
          .receipt-header {
            text-align: center;
            margin-bottom: 25px;
            border-bottom: 3px dashed #667eea;
            padding-bottom: 15px;
          }
          
          .receipt-header h1 {
            font-size: 24px;
            color: #667eea;
            margin-bottom: 5px;
          }
          
          .receipt-header p {
            font-size: 12px;
            color: #6b7280;
          }
          
          .receipt-body {
            margin-bottom: 20px;
          }
          
          .receipt-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            font-size: 14px;
          }
          
          .receipt-label {
            font-weight: 600;
            color: #1f2937;
          }
          
          .receipt-value {
            text-align: right;
            color: #6b7280;
            font-family: 'Courier New', monospace;
          }
          
          .receipt-row.highlight {
            background: #f3f4f6;
            padding: 10px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
          }
          
          .receipt-row.highlight .receipt-label {
            color: #667eea;
            font-size: 16px;
          }
          
          .receipt-row.highlight .receipt-value {
            color: #667eea;
            font-size: 20px;
            font-weight: bold;
          }
          
          .divider {
            border-top: 2px dashed #e5e7eb;
            margin: 15px 0;
          }
          
          .qr-section {
            text-align: center;
            margin: 20px 0;
            padding: 20px;
            background: #f9fafb;
            border-radius: 8px;
          }
          
          .qr-section h3 {
            font-size: 14px;
            color: #1f2937;
            margin-bottom: 15px;
          }
          
          #qrcode {
            display: inline-block;
            padding: 10px;
            background: white;
            border-radius: 6px;
          }
          
          .receipt-footer {
            text-align: center;
            font-size: 12px;
            color: #6b7280;
            border-top: 2px dashed #e5e7eb;
            padding-top: 15px;
            margin-top: 15px;
          }
          
          .receipt-footer p {
            margin-bottom: 8px;
          }
          
          .thank-you {
            font-size: 14px;
            font-weight: 600;
            color: #667eea;
            margin-bottom: 10px;
          }
          
          @media print {
            body {
              padding: 0;
            }
            
            .receipt-container {
              box-shadow: none;
              border: 1px solid #ccc;
            }
            
            button {
              display: none;
            }
          }
          
          .print-button {
            width: 100%;
            padding: 12px;
            margin-top: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
          }
          
          .print-button:hover {
            transform: translateY(-2px);
          }
          
          .close-button {
            width: 100%;
            padding: 10px;
            margin-top: 8px;
            background: #e5e7eb;
            color: #1f2937;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
          }
          
          .close-button:hover {
            background: #d1d5db;
          }
        </style>
      </head>
      <body>
        <div class="receipt-container">
          <div class="receipt-header">
            <h1>🅿️ PARKING RECEIPT</h1>
            <p>Smart Parking System</p>
          </div>
          
          <div class="receipt-body">
            <div class="receipt-row">
              <span class="receipt-label">License Plate:</span>
              <span class="receipt-value">${plate}</span>
            </div>
            
            <div class="receipt-row">
              <span class="receipt-label">Slot Number:</span>
              <span class="receipt-value">${slotNumber}</span>
            </div>
            
            <div class="divider"></div>
            
            <div class="receipt-row">
              <span class="receipt-label">Entry Time:</span>
              <span class="receipt-value">${entryTime}</span>
            </div>
            
            <div class="receipt-row">
              <span class="receipt-label">Exit Time:</span>
              <span class="receipt-value">${exitTime}</span>
            </div>
            
            <div class="receipt-row">
              <span class="receipt-label">Duration:</span>
              <span class="receipt-value">${duration} min</span>
            </div>
            
            <div class="divider"></div>
            
            <div class="receipt-row highlight">
              <span class="receipt-label">AMOUNT DUE:</span>
              <span class="receipt-value">₹${charge}</span>
            </div>
          </div>
          
          <div class="qr-section">
            <h3>📱 Scan to Pay</h3>
            <div id="qrcode"></div>
            <p style="margin-top: 10px; font-size: 12px; color: #6b7280;">
              5 Rupees per minute<br>
              Minimum: ₹10
            </p>
          </div>
          
          <div class="receipt-footer">
            <p class="thank-you">Thank You!</p>
            <p>For Smart Parking System</p>
            <p style="margin-top: 10px; font-size: 11px;">
              Receipt ID: ${txnId}<br>
              Generated: ${new Date().toLocaleString()}
            </p>
          </div>
          
          <button class="print-button" onclick="window.print()">🖨️ Print Receipt</button>
          <button class="close-button" onclick="window.close()">Close</button>
        </div>
        
        <script>
          // Generate QR code
          new QRCode(document.getElementById('qrcode'), {
            text: '${paymentData}',
            width: 200,
            height: 200,
            colorDark: '#667eea',
            colorLight: '#ffffff',
            correctLevel: QRCode.CorrectLevel.H
          });
        </script>
      </body>
      </html>
    `;
    
    printWindow.document.write(htmlContent);
    printWindow.document.close();
  }

  // Expose printReceipt to global scope
  window.printReceipt = printReceipt;

  // ...existing code in renderVehicleDetails...
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
      
      // CHANGED: Print button instead of Pay Now
      const actionBtn = vehicle.payment_status === 'pending' && vehicle.time_out !== 'Still Parked' ? 
        `<button class="print-btn" onclick="printReceipt(${vehicle.id}, '${vehicle.plate}', '${vehicle.slot_number}', '${vehicle.time_in}', '${vehicle.time_out}', ${vehicle.duration_minutes}, '${vehicle.charge.replace('₹', '')}')">🖨️ Print</button>` : 
        '<span style="color: #10b981;">✓ Paid</span>';

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

  // ...rest of existing code...
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