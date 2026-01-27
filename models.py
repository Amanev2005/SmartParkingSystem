from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='free')  # free/occupied
    current_txn_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'number': self.number,
            'status': self.status,
            'plate': None
        }

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
    
    def to_dict(self):
        return {
            'id': self.id,
            'plate': self.plate,
            'slot_number': self.slot.number if self.slot else None,
            'time_in': self.time_in.isoformat() if self.time_in else None,
            'time_out': self.time_out.isoformat() if self.time_out else None,
            'duration_minutes': self.duration_minutes,
            'charge': self.charge,
            'payment_status': self.payment_status,
            'status': 'exited' if self.time_out else 'parked'
        }