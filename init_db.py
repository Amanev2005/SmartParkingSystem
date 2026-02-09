from models import db, Slot, create_app

app = create_app()
with app.app_context():
    db.drop_all()
    db.create_all()

    # Create 60 slots
    slots = [Slot(number=i+1, status='free') for i in range(60)]
    db.session.add_all(slots)
    db.session.commit()
    print('✓ Database initialized with 60 slots')