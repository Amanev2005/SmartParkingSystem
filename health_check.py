import requests

try:
    r = requests.get('http://localhost:5000/api/health', timeout=2)
    print('STATUS', r.status_code)
    print(r.text)
except Exception as e:
    print('ERROR', e)
