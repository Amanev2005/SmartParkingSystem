# models.py
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from datetime import datetime

db = SQLAlchemy()

class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='free')  # free/occupied
    current_txn_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(128), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=True)
    time_in = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    time_out = db.Column(db.DateTime, nullable=True)
    charge = db.Column(db.Float, nullable=True)

    slot = db.relationship('Slot', foreign_keys=[slot_id], backref='transactions')


def create_app(sqlite_path='sqlite:///parking.db'):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = sqlite_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app
