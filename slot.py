from flask import Flask, render_template, request, jsonify
from models import db, Slot, Transaction, create_app
from datetime import datetime
import logging
import math
import threading
import os

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
            return {'success': False, 'error': 'No available slots', 'action': 'entry'}
        
        logger.info(f'[ENTRY] Found available slot: {available_slot.number}')
        
        txn = Transaction(plate=plate, slot_id=available_slot.id, time_in=datetime.utcnow())
        db.session.add(txn)
        db.session.flush()
        
        logger.info(f'[ENTRY] Transaction created with ID: {txn.id}')
        
        available_slot.status = 'occupied'
        available_slot.current_txn_id = txn.id
        db.session.commit()
        
        logger.info(f'[ENTRY] ✓ SUCCESS: Plate {plate} -> Slot {available_slot.number}')
        
        return {
            'success': True,
            'action': 'entry',
            'message': f'Vehicle {plate} ENTERED. Slot {available_slot.number} assigned.',
            'slot_id': available_slot.id,
            'slot_number': available_slot.number,
            'txn_id': txn.id
        }
    except Exception as e:
        db.session.rollback()
        logger.error(f'[ENTRY] ✗ Error for plate {plate}: {e}', exc_info=True)
        return {'success': False, 'error': str(e), 'action': 'entry'}

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
        
        return {
            'success': True,
            'action': 'exit',
            'message': f'Vehicle {plate} EXITED from Slot {txn.slot.number if txn.slot else "N/A"}',
            'duration_minutes': duration_minutes,
            'charge': txn.charge,
            'payment_status': 'pending',
            'slot_number': txn.slot.number if txn.slot else None
        }
    except Exception as e:
        db.session.rollback()
        logger.error(f'[EXIT] ✗ Error for plate {plate}: {e}', exc_info=True)
        return {'success': False, 'error': str(e), 'action': 'exit'}

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        slot_count = Slot.query.count()
        occupied_slots = Slot.query.filter_by(status='occupied').count()
        active_txns = Transaction.query.filter_by(time_out=None).count()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'connected': True,
                'total_slots': slot_count,
                'occupied': occupied_slots,
                'free': slot_count - occupied_slots,
                'active_vehicles': active_txns
            }
        }), 200
    
    except Exception as e:
        logger.error(f'[HEALTH] Error: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/detect', methods=['POST'])
def detect_plate():
    """Detect plate from video and allocate slot"""
    try:
        plate = request.form.get('plate')
        
        if not plate:
            return jsonify({'success': False, 'error': 'No plate provided'}), 400
        
        logger.info(f'[DETECT] Processing plate: {plate}')
        
        # Check if vehicle already parked
        existing = Transaction.query.filter_by(plate=plate, time_out=None).first()
        
        if existing:
            logger.warning(f'[DETECT] Vehicle {plate} already parked in slot {existing.slot.number}')
            return jsonify({
                'success': False,
                'error': 'Vehicle already in parking',
                'slot_number': existing.slot.number,
                'action': 'ALREADY_PARKED'
            }), 409
        
        # Find free slot
        free_slot = Slot.query.filter_by(status='free').first()
        
        if not free_slot:
            logger.error('[DETECT] No free slots available')
            return jsonify({
                'success': False,
                'error': 'Parking lot full',
                'action': 'FULL'
            }), 503
        
        # Create transaction
        txn = Transaction(
            plate=plate,
            slot_id=free_slot.id,
            time_in=datetime.now()
        )
        
        free_slot.status = 'occupied'
        free_slot.current_txn_id = txn.id
        
        db.session.add(txn)
        db.session.commit()
        
        logger.info(f'[ENTRY] Vehicle {plate} -> Slot {free_slot.number}')
        
        return jsonify({
            'success': True,
            'action': 'ENTRY',
            'slot_number': free_slot.number,
            'plate': plate,
            'transaction_id': txn.id,
            'message': f'Slot {free_slot.number} allocated'
        }), 200
    
    except Exception as e:
        logger.error(f'[DETECT] Error: {e}', exc_info=True)
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

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
        
        result = entry_vehicle_internal(plate)
        return jsonify(result)
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
        
        result = exit_vehicle_internal(plate, txn)
        return jsonify(result)
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

@app.route('/api/video/process', methods=['POST'])
def process_video():
    """Process uploaded video for plate detection"""
    try:
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': 'No video file provided'})
        
        video_file = request.files['video']
        
        # Save video temporarily
        temp_path = os.path.join('temp_videos', video_file.filename)
        os.makedirs('temp_videos', exist_ok=True)
        video_file.save(temp_path)
        
        # Process video
        from anpr_yolo_easyocr import process_video_stream
        
        detections = []
        
        def callback(plate_data):
            detections.append({
                'plate': plate_data['plate'],
                'timestamp': plate_data['timestamp'],
                'frame': plate_data['frame_number']
            })
        
        success = process_video_stream(temp_path, callback=callback, confidence_threshold=0.7)
        
        # Clean up
        try:
            os.remove(temp_path)
        except:
            pass
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Video processed. Found {len(detections)} plates.',
                'detections': detections
            })
        else:
            return jsonify({'success': False, 'error': 'Video processing failed'})
            
    except Exception as e:
        logger.error(f'Video processing error: {e}')
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/camera/start', methods=['POST'])
def start_camera():
    """Start camera for real-time processing"""
    try:
        camera_source = request.form.get('source', '0')
        
        # Start processing in background thread
        from anpr_yolo_easyocr import process_video_realtime
        
        def process_thread():
            process_video_realtime(camera_source, display=True)
        
        thread = threading.Thread(target=process_thread, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Camera processing started on source {camera_source}',
            'thread_alive': thread.is_alive()
        })
        
    except Exception as e:
        logger.error(f'Camera start error: {e}')
        return jsonify({'success': False, 'error': str(e)})

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