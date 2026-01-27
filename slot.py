from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import logging
import math

# Initialize Flask app and database
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define models
class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='free')  # free/occupied
    current_txn_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(128), nullable=False, index=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=True)
    time_in = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    time_out = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    charge = db.Column(db.Float, nullable=True)
    payment_status = db.Column(db.String(20), nullable=False, default='pending')  # pending/paid/failed
    
    slot = db.relationship('Slot', foreign_keys=[slot_id], backref='transactions')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
RATE_PER_MINUTE = 5.0  # 5 rupees per minute
MIN_CHARGE = 10.0  # Minimum charge

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
                if txn:
                    slot_data['plate'] = txn.plate
            result.append(slot_data)
        return jsonify(result)
    except Exception as e:
        logger.error(f'Get slots error: {e}')
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/detect', methods=['POST'])
def detect_plate():
    """
    Universal endpoint for plate detection.
    Logic:
    1. Check if plate exists in database with time_out=None (active transaction)
    2. If EXISTS -> Process as EXIT (release slot)
    3. If NOT EXISTS -> Process as ENTRY (allocate slot)
    """
    plate = request.form.get('plate', '').strip().upper()
    
    if not plate:
        return jsonify({'success': False, 'error': 'Plate number required'})
    
    logger.info(f'[DETECT] Plate detected: {plate}')
    
    try:
        # Check if vehicle already has active transaction (parked inside)
        existing_txn = Transaction.query.filter_by(plate=plate, time_out=None).first()
        
        if existing_txn:
            # VEHICLE ALREADY INSIDE -> PROCESS AS EXIT
            logger.info(f'[DETECT] Plate {plate} FOUND in database with active transaction. Processing as EXIT.')
            return exit_vehicle_internal(plate, existing_txn)
        else:
            # VEHICLE NOT IN DATABASE OR ALREADY EXITED -> PROCESS AS ENTRY
            logger.info(f'[DETECT] Plate {plate} NOT found in database. Processing as ENTRY.')
            return entry_vehicle_internal(plate)
            
    except Exception as e:
        db.session.rollback()
        logger.error(f'[DETECT] Error: {e}')
        return jsonify({'success': False, 'error': str(e)})

def entry_vehicle_internal(plate):
    """Internal function to register vehicle entry"""
    try:
        logger.info(f'[ENTRY] Starting entry process for plate: {plate}')
        
        # Find available slot
        available_slot = Slot.query.filter_by(status='free').first()
        if not available_slot:
            logger.warning(f'[ENTRY] No available slots for plate: {plate}')
            return jsonify({'success': False, 'error': 'No available slots', 'action': 'entry'})
        
        logger.info(f'[ENTRY] Found available slot: {available_slot.number}')
        
        # Create transaction
        txn = Transaction(plate=plate, slot_id=available_slot.id, time_in=datetime.utcnow())
        db.session.add(txn)
        db.session.flush()
        
        logger.info(f'[ENTRY] Transaction created with ID: {txn.id}')
        
        # Update slot
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
        logger.error(f'[ENTRY] ✗ Error for plate {plate}: {e}')
        return jsonify({'success': False, 'error': str(e), 'action': 'entry'})

def exit_vehicle_internal(plate, txn):
    """Internal function to register vehicle exit"""
    try:
        logger.info(f'[EXIT] Starting exit process for plate: {plate}')
        
        # Update transaction
        txn.time_out = datetime.utcnow()
        duration_seconds = (txn.time_out - txn.time_in).total_seconds()
        duration_minutes = math.ceil(duration_seconds / 60.0)
        
        # Calculate charge: 5 rupees per minute with minimum 10 rupees
        charge = max(MIN_CHARGE, duration_minutes * RATE_PER_MINUTE)
        
        txn.duration_minutes = duration_minutes
        txn.charge = round(charge, 2)
        txn.payment_status = 'pending'  # New vehicle exits with pending payment
        
        logger.info(f'[EXIT] Duration: {duration_minutes}m, Charge: ₹{charge}')
        
        # Release slot
        if txn.slot_id:
            slot = Slot.query.get(txn.slot_id)
            if slot:
                slot.status = 'free'
                slot.current_txn_id = None
                logger.info(f'[EXIT] Slot {slot.number} released')
        
        db.session.commit()
        
        logger.info(f'[EXIT] ✓ SUCCESS: Plate {plate} EXITED from Slot {txn.slot.number if txn.slot else "N/A"}, Charge: ₹{charge}')
        
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
        logger.error(f'[EXIT] ✗ Error for plate {plate}: {e}')
        return jsonify({'success': False, 'error': str(e), 'action': 'exit'})

@app.route('/api/entry', methods=['POST'])
def manual_entry():
    """Manual entry endpoint - called from admin panel form"""
    plate = request.form.get('plate', '').strip().upper()
    
    if not plate:
        return jsonify({'success': False, 'error': 'Plate number required', 'action': 'entry'})
    
    logger.info(f'[MANUAL ENTRY] Plate: {plate}')
    
    try:
        # Check if vehicle already has active transaction
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
        logger.error(f'[MANUAL ENTRY] Error: {e}')
        return jsonify({'success': False, 'error': str(e), 'action': 'entry'})

@app.route('/api/exit', methods=['POST'])
def manual_exit():
    """Manual exit endpoint - called from admin panel form"""
    plate = request.form.get('plate', '').strip().upper()
    
    if not plate:
        return jsonify({'success': False, 'error': 'Plate number required', 'action': 'exit'})
    
    logger.info(f'[MANUAL EXIT] Plate: {plate}')
    
    try:
        # Find active transaction for this plate
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
        logger.error(f'[MANUAL EXIT] Error: {e}')
        return jsonify({'success': False, 'error': str(e), 'action': 'exit'})

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions (for history/reporting)"""
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
        logger.error(f'Transactions error: {e}')
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vehicle-details', methods=['GET'])
def get_vehicle_details():
    """Get detailed vehicle information for admin panel"""
    try:
        # Get all transactions with details
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
        logger.error(f'Vehicle details error: {e}')
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/payment/status/<int:txn_id>', methods=['GET'])
def get_payment_status(txn_id):
    """Get payment status for a specific transaction"""
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
        logger.error(f'Payment status error: {e}')
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/payment/process/<int:txn_id>', methods=['POST'])
def process_payment(txn_id):
    """Process payment for a transaction"""
    try:
        txn = Transaction.query.get(txn_id)
        if not txn:
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404
        
        # Update payment status
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
        logger.error(f'Payment processing error: {e}')
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
    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
        
        # Check if slots exist, if not create them
        slot_count = Slot.query.count()
        if slot_count == 0:
            logger.info('Creating 60 parking slots...')
            slots = [Slot(number=i+1, status='free') for i in range(60)]
            db.session.add_all(slots)
            db.session.commit()
            logger.info('60 slots created successfully')
    
    logger.info('Starting Flask server on http://localhost:5000')
    app.run(debug=True, host='localhost', port=5000)