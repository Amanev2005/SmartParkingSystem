from flask import jsonify, request, render_template
from models import create_app, db, Slot, Transaction
from datetime import datetime
from qr_payment import generate_qr
import math

app = create_app()
RATE_PER_HOUR = 20.0
MIN_CHARGE = 10.0

@app.route('/')
def index():
    return render_template('index.html')
# ...existing code...
@app.route('/api/slots')
def api_slots():
    # returns list of slots used by static/js/main.js
    slots = Slot.query.order_by(Slot.number).all()
    return jsonify([{'id': s.id, 'number': s.number, 'status': s.status} for s in slots])

@app.route('/api/entry', methods=['POST'])
def vehicle_entry():
    plate = request.form.get('plate')
    if not plate:
        return jsonify({'success': False, 'error': 'No plate provided'}), 400
    plate = plate.strip().upper()

    open_txn = Transaction.query.filter_by(plate=plate, time_out=None).first()
    if open_txn:
        return jsonify({'success': False, 'error': 'Vehicle already parked'}), 400

    slot = Slot.query.filter_by(status='free').order_by(Slot.number).first()
    if not slot:
        return jsonify({'success': False, 'error': 'Parking full'}), 400

    txn = Transaction(plate=plate, slot_id=slot.id, time_in=datetime.utcnow())
    db.session.add(txn)
    db.session.flush()
    slot.status = 'occupied'
    slot.current_txn_id = txn.id
    db.session.commit()
    return jsonify({'success': True, 'plate': plate, 'slot': slot.number, 'time_in': txn.time_in.isoformat()})
    qr_path = generate_qr(txn.charge, txn.id)

@app.route('/api/exit', methods=['POST'])
def vehicle_exit():
    plate = request.form.get('plate')
    if not plate:
        return jsonify({'success': False, 'error': 'No plate provided'}), 400
    plate = plate.strip().upper()

    txn = Transaction.query.filter_by(plate=plate, time_out=None).first()
    if not txn:
        return jsonify({'success': False, 'error': 'No active parking record for this plate'}), 404

    txn.time_out = datetime.utcnow()
    duration_seconds = (txn.time_out - txn.time_in).total_seconds()
    minutes = math.ceil(duration_seconds / 60.0)
    charge = max(MIN_CHARGE, (RATE_PER_HOUR / 60.0) * minutes)
    txn.charge = round(charge, 2)

    slot = Slot.query.get(txn.slot_id)
    if slot:
        slot.status = 'free'
        slot.current_txn_id = None

    db.session.commit()
    return jsonify({'success': True, 'plate': plate, 'time_in': txn.time_in.isoformat(), 'time_out': txn.time_out.isoformat(), 'duration_minutes': minutes, 'charge': txn.charge})

@app.route('/api/status')
def status():
    slots = Slot.query.order_by(Slot.number).all()
    out = []
    for s in slots:
        out.append({'number': s.number, 'status': s.status})
    return jsonify({'slots': out})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)