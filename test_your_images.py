import sys
from anpr_yolo_easyocr import process_image_batch

images = [
    r"c:\Users\Labeeb\Pictures\number-plate\car1.jpg",
    r"c:\Users\Labeeb\Pictures\number-plate\car2.webp",
    r"c:\Users\Labeeb\Pictures\number-plate\car3.jpg",
    r"c:\Users\Labeeb\Pictures\number-plate\car4.jpg",
    r"c:\Users\Labeeb\Pictures\number-plate\car5.jpg",
    r"c:\Users\Labeeb\Pictures\number-plate\car6.jpg",
    r"c:\Users\Labeeb\Pictures\number-plate\car7.jpg",
    r"c:\Users\Labeeb\Pictures\number-plate\car8.jpg",
]

print("\n" + "="*70)
print("TESTING PLATE DETECTION WITH YOUR IMAGES")
print("="*70 + "\n")

results = process_image_batch(images)

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
for result in results:
    status = "✓" if result['plate'] else "✗"
    plate = result['plate'] or "NO DETECTION"
    print(f"{status} {result['image'].split(chr(92))[-1]}: {plate}")
print("="*70)