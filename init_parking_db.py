#!/usr/bin/env python
"""
Initialize parking database with slots
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    try:
        from models import create_app, db, Slot
        
        app = create_app()
        
        with app.app_context():
            # Create all tables
            db.create_all()
            logger.info("✓ Database tables created")
            
            # Check existing slots
            existing = Slot.query.count()
            
            if existing == 0:
                logger.info("Creating 10 parking slots...")
                for i in range(1, 11):
                    slot = Slot(number=i, status='free')
                    db.session.add(slot)
                db.session.commit()
                logger.info(f"✓ Created 10 parking slots")
            else:
                logger.info(f"✓ Database already has {existing} slots")
                
                # Reset all slots to free
                slots = Slot.query.all()
                for slot in slots:
                    slot.status = 'free'
                    slot.current_txn_id = None
                db.session.commit()
                logger.info("✓ Reset all slots to FREE")
            
            # Show status
            from models import Transaction
            txns = Transaction.query.filter_by(time_out=None).count()
            logger.info(f"✓ Active transactions: {txns}")
            logger.info("✓ Database initialization complete\n")
            
        return True
        
    except Exception as e:
        logger.error(f"✗ Database error: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    logger.info("="*70)
    logger.info("INITIALIZING PARKING DATABASE")
    logger.info("="*70 + "\n")
    
    success = init_db()
    
    if success:
        logger.info("✓ Ready to start detection")
        logger.info("\nRun detection with:")
        logger.info("  python camera_capture.py --photo --dedup 20")
        logger.info("  python camera_capture.py --local 0 --dedup 20")
        sys.exit(0)
    else:
        logger.error("✗ Failed to initialize database")
        sys.exit(1)
