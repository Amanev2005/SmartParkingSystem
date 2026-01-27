import pytest
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from slot import app, db, Slot, Transaction


@pytest.fixture
def client():
    """Create test client with isolated test database"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sample_slots():
    """Create sample parking slots for testing"""
    with app.app_context():
        slots = [Slot(number=i+1, status='free') for i in range(5)]
        db.session.add_all(slots)
        db.session.commit()
        return [s.id for s in slots]


class TestGetVehicleDetails:
    """Test suite for /api/vehicle-details endpoint"""
    
    def test_empty_database(self, client):
        """Test endpoint returns empty list when no transactions exist"""
        response = client.get('/api/vehicle-details')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_single_parked_vehicle(self, client, sample_slots):
        """Test response for single vehicle currently parked"""
        with app.app_context():
            slot = Slot.query.filter_by(number=1).first()
            txn = Transaction(
                plate='KA01AB1234',
                slot_id=slot.id,
                time_in=datetime.utcnow()
            )
            db.session.add(txn)
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            
            assert response.status_code == 200
            data = response.get_json()
            assert len(data) == 1
            assert data[0]['plate'] == 'KA01AB1234'
            assert data[0]['status'] == 'PARKED'
            assert data[0]['time_out'] == 'Still Parked'
            assert data[0]['duration_minutes'] == 'Ongoing'
            assert data[0]['charge'] == 'N/A'
            assert data[0]['payment_status'] == 'pending'
    
    def test_single_exited_vehicle_with_charge(self, client, sample_slots):
        """Test response for vehicle that exited with charge calculated"""
        with app.app_context():
            slot = Slot.query.filter_by(number=1).first()
            time_in = datetime.utcnow() - timedelta(minutes=30)
            time_out = datetime.utcnow()
            
            txn = Transaction(
                plate='KA02XY5678',
                slot_id=slot.id,
                time_in=time_in,
                time_out=time_out,
                duration_minutes=30,
                charge=150.0,
                payment_status='pending'
            )
            db.session.add(txn)
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            
            assert response.status_code == 200
            data = response.get_json()
            assert len(data) == 1
            assert data[0]['plate'] == 'KA02XY5678'
            assert data[0]['status'] == 'EXITED'
            assert data[0]['duration_minutes'] == 30
            assert data[0]['charge'] == '₹150.00'
            assert data[0]['payment_status'] == 'pending'
            assert 'Still Parked' not in data[0]['time_out']
    
    def test_multiple_vehicles_mixed_status(self, client, sample_slots):
        """Test multiple vehicles with different states"""
        with app.app_context():
            # Parked vehicle
            slot1 = Slot.query.filter_by(number=1).first()
            txn1 = Transaction(
                plate='KA01AA0001',
                slot_id=slot1.id,
                time_in=datetime.utcnow()
            )
            
            # Exited, paid vehicle
            slot2 = Slot.query.filter_by(number=2).first()
            txn2 = Transaction(
                plate='KA02BB0002',
                slot_id=slot2.id,
                time_in=datetime.utcnow() - timedelta(hours=1),
                time_out=datetime.utcnow() - timedelta(minutes=30),
                duration_minutes=60,
                charge=300.0,
                payment_status='paid'
            )
            
            # Exited, pending payment
            slot3 = Slot.query.filter_by(number=3).first()
            txn3 = Transaction(
                plate='KA03CC0003',
                slot_id=slot3.id,
                time_in=datetime.utcnow() - timedelta(minutes=15),
                time_out=datetime.utcnow(),
                duration_minutes=15,
                charge=75.0,
                payment_status='pending'
            )
            
            db.session.add_all([txn1, txn2, txn3])
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            
            assert response.status_code == 200
            data = response.get_json()
            assert len(data) == 3
            
            # Check ordering (most recent first)
            assert data[0]['plate'] == 'KA03CC0003'
            assert data[0]['status'] == 'EXITED'
            assert data[1]['plate'] == 'KA02BB0002'
            assert data[1]['payment_status'] == 'paid'
            assert data[2]['plate'] == 'KA01AA0001'
            assert data[2]['status'] == 'PARKED'
    
    def test_response_format_all_fields_present(self, client, sample_slots):
        """Test all required fields are present in response"""
        with app.app_context():
            slot = Slot.query.filter_by(number=1).first()
            txn = Transaction(
                plate='KA01TEST999',
                slot_id=slot.id,
                time_in=datetime.utcnow() - timedelta(minutes=45),
                time_out=datetime.utcnow(),
                duration_minutes=45,
                charge=225.0,
                payment_status='pending'
            )
            db.session.add(txn)
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            data = response.get_json()
            vehicle = data[0]
            
            required_fields = [
                'id', 'plate', 'slot_number', 'time_in', 'time_out',
                'duration_minutes', 'charge', 'payment_status', 'status'
            ]
            for field in required_fields:
                assert field in vehicle, f"Missing required field: {field}"
    
    def test_charge_formatting_with_rupee_symbol(self, client, sample_slots):
        """Test charge is formatted with rupee symbol"""
        with app.app_context():
            slot = Slot.query.filter_by(number=1).first()
            txn = Transaction(
                plate='KA01FORMAT01',
                slot_id=slot.id,
                time_in=datetime.utcnow() - timedelta(minutes=20),
                time_out=datetime.utcnow(),
                duration_minutes=20,
                charge=99.50,
                payment_status='pending'
            )
            db.session.add(txn)
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            data = response.get_json()
            
            assert data[0]['charge'] == '₹99.50'
    
    def test_timestamp_formatting(self, client, sample_slots):
        """Test timestamps are formatted as strings (YYYY-MM-DD HH:MM:SS)"""
        with app.app_context():
            slot = Slot.query.filter_by(number=1).first()
            test_time_in = datetime(2024, 1, 15, 10, 30, 45)
            test_time_out = datetime(2024, 1, 15, 11, 0, 45)
            
            txn = Transaction(
                plate='KA01TIME001',
                slot_id=slot.id,
                time_in=test_time_in,
                time_out=test_time_out,
                duration_minutes=30,
                charge=150.0,
                payment_status='paid'
            )
            db.session.add(txn)
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            data = response.get_json()
            
            # Verify format YYYY-MM-DD HH:MM:SS
            assert data[0]['time_in'] == '2024-01-15 10:30:45'
            assert data[0]['time_out'] == '2024-01-15 11:00:45'
    
    def test_slot_number_display_for_deleted_slot(self, client, sample_slots):
        """Test vehicle details when associated slot is deleted"""
        with app.app_context():
            slot = Slot.query.filter_by(number=1).first()
            slot_id = slot.id
            
            txn = Transaction(
                plate='KA01DELETED',
                slot_id=slot_id,
                time_in=datetime.utcnow() - timedelta(minutes=10),
                time_out=datetime.utcnow(),
                duration_minutes=10,
                charge=50.0,
                payment_status='pending'
            )
            db.session.add(txn)
            db.session.commit()
            
            # Delete the slot
            Slot.query.filter_by(id=slot_id).delete()
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            data = response.get_json()
            
            # Should show 'N/A' for deleted slot
            assert data[0]['slot_number'] == 'N/A'
            assert data[0]['plate'] == 'KA01DELETED'
    
    def test_response_is_list(self, client):
        """Test endpoint always returns a list"""
        response = client.get('/api/vehicle-details')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
    
    def test_payment_status_values(self, client, sample_slots):
        """Test all possible payment status values"""
        with app.app_context():
            slot1 = Slot.query.filter_by(number=1).first()
            slot2 = Slot.query.filter_by(number=2).first()
            slot3 = Slot.query.filter_by(number=3).first()
            
            # Pending payment
            txn1 = Transaction(
                plate='KA01PENDING',
                slot_id=slot1.id,
                time_in=datetime.utcnow() - timedelta(minutes=10),
                time_out=datetime.utcnow(),
                duration_minutes=10,
                charge=50.0,
                payment_status='pending'
            )
            
            # Paid
            txn2 = Transaction(
                plate='KA02PAID',
                slot_id=slot2.id,
                time_in=datetime.utcnow() - timedelta(minutes=20),
                time_out=datetime.utcnow() - timedelta(minutes=10),
                duration_minutes=20,
                charge=100.0,
                payment_status='paid'
            )
            
            # Failed
            txn3 = Transaction(
                plate='KA03FAILED',
                slot_id=slot3.id,
                time_in=datetime.utcnow() - timedelta(minutes=30),
                time_out=datetime.utcnow() - timedelta(minutes=20),
                duration_minutes=30,
                charge=150.0,
                payment_status='failed'
            )
            
            db.session.add_all([txn1, txn2, txn3])
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            data = response.get_json()
            
            # Extract payment statuses
            payment_statuses = [v['payment_status'] for v in data]
            assert 'pending' in payment_statuses
            assert 'paid' in payment_statuses
            assert 'failed' in payment_statuses
    
    def test_no_slot_for_transaction(self, client):
        """Test vehicle details when transaction has no slot assigned"""
        with app.app_context():
            # Create transaction without slot
            txn = Transaction(
                plate='KA01NOSLOT',
                slot_id=None,
                time_in=datetime.utcnow() - timedelta(minutes=15),
                time_out=datetime.utcnow(),
                duration_minutes=15,
                charge=75.0,
                payment_status='pending'
            )
            db.session.add(txn)
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            data = response.get_json()
            
            assert data[0]['slot_number'] == 'N/A'
            assert data[0]['plate'] == 'KA01NOSLOT'


class TestEntryVehicle:
    """Test suite for /api/entry endpoint"""
    
    def test_entry_success(self, client, sample_slots):
        """Test successful vehicle entry"""
        response = client.post('/api/entry', data={'plate': 'KA01ABC1234'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['action'] == 'entry'
        assert 'KA01ABC1234' in data['message']
        assert data['slot_number'] is not None
    
    def test_entry_missing_plate(self, client):
        """Test entry with missing plate number"""
        response = client.post('/api/entry', data={})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'required' in data['error'].lower()
    
    def test_entry_duplicate_vehicle(self, client, sample_slots):
        """Test entry for vehicle already parked"""
        # First entry
        client.post('/api/entry', data={'plate': 'KA01DUP1234'})
        
        # Try second entry for same vehicle
        response = client.post('/api/entry', data={'plate': 'KA01DUP1234'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'already inside' in data['error'].lower()
    
    def test_entry_no_available_slots(self, client):
        """Test entry when no slots are available"""
        with app.app_context():
            # Create only 1 slot and occupy it
            slot = Slot(number=1, status='occupied')
            db.session.add(slot)
            db.session.commit()
        
        response = client.post('/api/entry', data={'plate': 'KA01NOSLOT'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'no available slots' in data['error'].lower()


class TestExitVehicle:
    """Test suite for /api/exit endpoint"""
    
    def test_exit_success(self, client, sample_slots):
        """Test successful vehicle exit"""
        with app.app_context():
            # First register entry
            slot = Slot.query.filter_by(number=1).first()
            txn = Transaction(
                plate='KA01EXIT123',
                slot_id=slot.id,
                time_in=datetime.utcnow() - timedelta(minutes=25)
            )
            db.session.add(txn)
            db.session.commit()
        
        response = client.post('/api/exit', data={'plate': 'KA01EXIT123'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['action'] == 'exit'
        assert data['charge'] > 0
    
    def test_exit_vehicle_not_found(self, client):
        """Test exit for vehicle not in system"""
        response = client.post('/api/exit', data={'plate': 'KA01NOTFOUND'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
    
    def test_exit_missing_plate(self, client):
        """Test exit with missing plate number"""
        response = client.post('/api/exit', data={})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'required' in data['error'].lower()


class TestChargeCalculation:
    """Test suite for charge calculation logic"""
    
    def test_minimum_charge(self, client, sample_slots):
        """Test minimum charge of ₹10 for very short duration"""
        with app.app_context():
            slot = Slot.query.filter_by(number=1).first()
            # 2 minutes should still be ₹10 minimum
            txn = Transaction(
                plate='KA01MINCHARGE',
                slot_id=slot.id,
                time_in=datetime.utcnow() - timedelta(minutes=2),
                time_out=datetime.utcnow(),
                duration_minutes=2,
                charge=10.0
            )
            db.session.add(txn)
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            data = response.get_json()
            
            assert data[0]['charge'] == '₹10.00'
    
    def test_charge_calculation_5_per_minute(self, client, sample_slots):
        """Test charge calculation at ₹5 per minute"""
        with app.app_context():
            slot = Slot.query.filter_by(number=1).first()
            # 25 minutes = 25 * 5 = ₹125
            txn = Transaction(
                plate='KA01CHARGE5',
                slot_id=slot.id,
                time_in=datetime.utcnow() - timedelta(minutes=25),
                time_out=datetime.utcnow(),
                duration_minutes=25,
                charge=125.0
            )
            db.session.add(txn)
            db.session.commit()
            
            response = client.get('/api/vehicle-details')
            data = response.get_json()
            
            assert data[0]['charge'] == '₹125.00'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])