import qrcode
import os

QR_DIR = "static/qr"

def generate_qr(amount, txn_id):
    # Changed from UPI to simple PIN message
    # We don't have the PIN here yet, but we can structure it similarly
    qr_data = f"PARKING-TXN:{txn_id}-AMT:{amount}"

    if not os.path.exists(QR_DIR):
        os.makedirs(QR_DIR)

    qr_path = f"{QR_DIR}/txn_{txn_id}.png"
    img = qrcode.make(qr_data)
    img.save(qr_path)

    return qr_path
