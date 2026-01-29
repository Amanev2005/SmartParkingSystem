from flask import Flask, render_template, request, jsonify
from models import db, Slot, Transaction, create_app
from datetime import datetime
import logging
import math

# Use the app factory from models.py
app = create_app()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
RATE_PER_MINUTE = 5.0
MIN_CHARGE = 10.0

@app.route('/')
def index():
    """Serve the main dashboard page"""
    return render_template('index.html')

@app.route('/api/slots', methods=['GET'])
def get_slots():
    """Get all parking slots with current status"""
    try:
        slots = Slot.query.all()
        result = []
        for slot in slots:
            slot_data = {
                'id': slot.id,
                'number': slot.number,
                'status': slot.status,
                'plate': None
            }
            if slot.current_txn_id:
                txn = Transaction.query.get(slot.current_txn_id)
                if txn and txn.time_out is None:
                    slot_data['plate'] = txn.plate
            result.append(slot_data)
        logger.info(f'[SLOTS] Returned {len(result)} slots')
        return jsonify(result)
    except Exception as e:
        logger.error(f'Get slots error: {e}')
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/debug/slots', methods=['GET'])
def debug_slots():
    """Debug endpoint to check all slots and transactions"""
    try:
        slots = Slot.query.all()
        txns = Transaction.query.all()
        
        slots_info = []
        for slot in slots:
            slots_info.append({
                'id': slot.id,
                'number': slot.number,
                'status': slot.status,
                'current_txn_id': slot.current_txn_id,
                'txn_plate': Transaction.query.get(slot.current_txn_id).plate if slot.current_txn_id else None
            })
        
        txns_info = []
        for txn in txns:
            txns_info.append({
                'id': txn.id,
                'plate': txn.plate,
                'slot_id': txn.slot_id,
                'time_in': str(txn.time_in),
                'time_out': str(txn.time_out) if txn.time_out else None,
                'payment_status': txn.payment_status
            })
        
        return jsonify({
            'slots': slots_info,
            'transactions': txns_info,
            'total_slots': len(slots),
            'occupied': len([s for s in slots if s.status == 'occupied']),
            'free': len([s for s in slots if s.status == 'free'])
        })
    except Exception as e:
        logger.error(f'Debug error: {e}')
        return jsonify({'error': str(e)})

def entry_vehicle_internal(plate):
    """Internal function to register vehicle entry"""
    try:
        logger.info(f'[ENTRY] Starting entry process for plate: {plate}')
        
        available_slot = Slot.query.filter_by(status='free').first()
        if not available_slot:
            logger.warning(f'[ENTRY] No available slots for plate: {plate}')
            return jsonify({'success': False, 'error': 'No available slots', 'action': 'entry'})
        
        logger.info(f'[ENTRY] Found available slot: {available_slot.number}')
        
        txn = Transaction(plate=plate, slot_id=available_slot.id, time_in=datetime.utcnow())
        db.session.add(txn)
        db.session.flush()
        
        logger.info(f'[ENTRY] Transaction created with ID: {txn.id}')
        
        available_slot.status = 'occupied'
        available_slot.current_txn_id = txn.id
        db.session.commit()
        
        logger.info(f'[ENTRY] ✓ SUCCESS: Plate {plate} -> Slot {available_slot.number}')
        
        return jsonify({
            'success': True,
            'action': 'entry',
            'message': f'Vehicle {plate} ENTERED. Slot {available_slot.number} assigned.',
            'slot_id': available_slot.id,
            'slot_number': available_slot.number,
            'txn_id': txn.id
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f'[ENTRY] ✗ Error for plate {plate}: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e), 'action': 'entry'})

def exit_vehicle_internal(plate, txn):
    """Internal function to register vehicle exit"""
    try:
        logger.info(f'[EXIT] Starting exit process for plate: {plate}')
        
        txn.time_out = datetime.utcnow()
        duration_seconds = (txn.time_out - txn.time_in).total_seconds()
        duration_minutes = math.ceil(duration_seconds / 60.0)
        
        charge = max(MIN_CHARGE, duration_minutes * RATE_PER_MINUTE)
        
        txn.duration_minutes = duration_minutes
        txn.charge = round(charge, 2)
        txn.payment_status = 'pending'
        
        logger.info(f'[EXIT] Duration: {duration_minutes}m, Charge: ₹{charge}')
        
        if txn.slot_id:
            slot = Slot.query.get(txn.slot_id)
            if slot:
                slot.status = 'free'
                slot.current_txn_id = None
                logger.info(f'[EXIT] Slot {slot.number} released')
        
        db.session.commit()
        
        logger.info(f'[EXIT] ✓ SUCCESS: Plate {plate} EXITED, Charge: ₹{charge}')
        
        return jsonify({
            'success': True,
            'action': 'exit',
            'message': f'Vehicle {plate} EXITED from Slot {txn.slot.number if txn.slot else "N/A"}',
            'duration_minutes': duration_minutes,
            'charge': txn.charge,
            'payment_status': 'pending',
            'slot_number': txn.slot.number if txn.slot else None
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f'[EXIT] ✗ Error for plate {plate}: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e), 'action': 'exit'})

@app.route('/api/detect', methods=['POST'])
def detect_plate():
    """Universal endpoint for plate detection"""
    plate = request.form.get('plate', '').strip().upper()
    
    if not plate:
        return jsonify({'success': False, 'error': 'Plate number required'})
    
    logger.info(f'[DETECT] Plate detected: {plate}')
    
    try:
        existing_txn = Transaction.query.filter_by(plate=plate, time_out=None).first()
        
        if existing_txn:
            logger.info(f'[DETECT] Plate {plate} FOUND. Processing as EXIT.')
            return exit_vehicle_internal(plate, existing_txn)
        else:
            logger.info(f'[DETECT] Plate {plate} NOT found. Processing as ENTRY.')
            return entry_vehicle_internal(plate)
            
    except Exception as e:
        db.session.rollback()
        logger.error(f'[DETECT] Error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/entry', methods=['POST'])
def manual_entry():
    """Manual entry endpoint"""
    plate = request.form.get('plate', '').strip().upper()
    
    if not plate:
        return jsonify({'success': False, 'error': 'Plate number required', 'action': 'entry'})
    
    logger.info(f'[MANUAL ENTRY] Plate: {plate}')
    
    try:
        existing_txn = Transaction.query.filter_by(plate=plate, time_out=None).first()
        if existing_txn:
            return jsonify({
                'success': False, 
                'error': f'Vehicle {plate} already inside. Use EXIT to remove.',
                'action': 'entry'
            })
        
        return entry_vehicle_internal(plate)
    except Exception as e:
        db.session.rollback()
        logger.error(f'[MANUAL ENTRY] Error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e), 'action': 'entry'})

@app.route('/api/exit', methods=['POST'])
def manual_exit():
    """Manual exit endpoint"""
    plate = request.form.get('plate', '').strip().upper()
    
    if not plate:
        return jsonify({'success': False, 'error': 'Plate number required', 'action': 'exit'})
    
    logger.info(f'[MANUAL EXIT] Plate: {plate}')
    
    try:
        txn = Transaction.query.filter_by(plate=plate, time_out=None).first()
        if not txn:
            return jsonify({
                'success': False, 
                'error': f'No active transaction found for plate {plate}',
                'action': 'exit'
            })
        
        return exit_vehicle_internal(plate, txn)
    except Exception as e:
        db.session.rollback()
        logger.error(f'[MANUAL EXIT] Error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e), 'action': 'exit'})

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions"""
    try:
        txns = Transaction.query.order_by(Transaction.time_in.desc()).all()
        result = []
        for txn in txns:
            result.append({
                'id': txn.id,
                'plate': txn.plate,
                'slot_number': txn.slot.number if txn.slot else None,
                'time_in': txn.time_in.isoformat(),
                'time_out': txn.time_out.isoformat() if txn.time_out else None,
                'duration_minutes': txn.duration_minutes,
                'charge': txn.charge,
                'payment_status': txn.payment_status,
                'status': 'exited' if txn.time_out else 'parked'
            })
        return jsonify(result)
    except Exception as e:
        logger.error(f'Transactions error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vehicle-details', methods=['GET'])
def get_vehicle_details():
    """Get detailed vehicle information"""
    try:
        txns = Transaction.query.order_by(Transaction.time_in.desc()).all()
        result = []
        
        for txn in txns:
            vehicle_detail = {
                'id': txn.id,
                'plate': txn.plate,
                'slot_number': txn.slot.number if txn.slot else 'N/A',
                'time_in': txn.time_in.strftime('%Y-%m-%d %H:%M:%S') if txn.time_in else None,
                'time_out': txn.time_out.strftime('%Y-%m-%d %H:%M:%S') if txn.time_out else 'Still Parked',
                'duration_minutes': txn.duration_minutes if txn.duration_minutes else 'Ongoing',
                'charge': f'₹{txn.charge:.2f}' if txn.charge else 'N/A',
                'payment_status': txn.payment_status,
                'status': 'EXITED' if txn.time_out else 'PARKED'
            }
            result.append(vehicle_detail)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f'Vehicle details error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/payment/status/<int:txn_id>', methods=['GET'])
def get_payment_status(txn_id):
    """Get payment status"""
    try:
        txn = Transaction.query.get(txn_id)
        if not txn:
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404
        
        return jsonify({
            'success': True,
            'txn_id': txn.id,
            'plate': txn.plate,
            'charge': txn.charge,
            'payment_status': txn.payment_status
        })
    except Exception as e:
        logger.error(f'Payment status error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/payment/process/<int:txn_id>', methods=['POST'])
def process_payment(txn_id):
    """Process payment for a transaction"""
    try:
        txn = Transaction.query.get(txn_id)
        if not txn:
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404
        
        txn.payment_status = 'paid'
        db.session.commit()
        
        logger.info(f'[PAYMENT] ✓ Payment processed for plate {txn.plate}, Amount: ₹{txn.charge}')
        
        return jsonify({
            'success': True,
            'message': f'Payment of ₹{txn.charge} received for {txn.plate}',
            'payment_status': 'paid'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f'[PAYMENT] Payment processing error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        db.session.execute('SELECT 1')
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        slot_count = Slot.query.count()
        logger.info(f'[DB] Current slot count: {slot_count}')
        
        if slot_count == 0:
            logger.info('[DB] Creating 60 parking slots...')
            try:
                slots = [Slot(number=i+1, status='free') for i in range(60)]
                db.session.add_all(slots)
                db.session.commit()
                logger.info('[DB] ✓ 60 slots created successfully')
                
                verify_count = Slot.query.count()
                logger.info(f'[DB] Verification: {verify_count} slots in database')
            except Exception as e:
                logger.error(f'[DB] ✗ Error creating slots: {e}', exc_info=True)
                db.session.rollback()
        else:
            logger.info(f'[DB] ✓ Database already has {slot_count} slots')
    
    logger.info('Starting Flask server on http://localhost:5000')
    app.run(debug=True, host='localhost', port=5000)