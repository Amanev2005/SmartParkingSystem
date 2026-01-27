import qrcode
import os

QR_DIR = "static/qr"

def generate_qr(amount, txn_id):
    upi_url = (
        f"upi://pay?"
        f"pa=parking@upi&"
        f"pn=SmartParking&"
        f"am={amount}&"
        f"cu=INR&"
        f"tr=TXN{txn_id}"
    )

    if not os.path.exists(QR_DIR):
        os.makedirs(QR_DIR)

    qr_path = f"{QR_DIR}/txn_{txn_id}.png"
    img = qrcode.make(upi_url)
    img.save(qr_path)

    return qr_path
