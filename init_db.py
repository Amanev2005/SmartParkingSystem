#!/usr/bin/env python
"""
Initialize parking database with slots
"""
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_db():
    try:
        from models import db, Slot, Transaction, create_app
        
        app = create_app()
        
        with app.app_context():
            # Create all tables (drop_all if you want a completely fresh start)
            # db.drop_all() 
            db.create_all()
            logger.info("✓ Database tables verified/created")
            
            # Check existing slots
            existing = Slot.query.count()
            target_slots = 60
            
            if existing == 0:
                logger.info(f"Creating {target_slots} parking slots...")
                slots = [Slot(number=i+1, status='free') for i in range(target_slots)]
                db.session.add_all(slots)
                db.session.commit()
                logger.info(f"✓ Created {target_slots} parking slots")
            else:
                logger.info(f"✓ Database already has {existing} slots")
                
                # Reset all slots to free and clear transaction references
                slots = Slot.query.all()
                for slot in slots:
                    slot.status = 'free'
                    slot.current_txn_id = None
                
                # Clear active transactions if needed (optional)
                # Transaction.query.delete() 
                
                db.session.commit()
                logger.info("✓ Reset all slots to FREE and cleared active transaction references")
            
            # Show final status
            final_count = Slot.query.count()
            logger.info(f"✓ Database initialization complete: {final_count} slots ready\n")
            
        return True
        
    except Exception as e:
        logger.error(f"✗ Database error: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    logger.info("="*70)
    logger.info("INITIALIZING SMART PARKING DATABASE")
    logger.info("="*70 + "\n")
    
    success = init_db()
    
    if success:
        logger.info("✓ System ready to start")
        sys.exit(0)
    else:
        logger.error("✗ Failed to initialize database")
        sys.exit(1)
