import urllib.request
import json

def check(url):
    try:
        req = urllib.request.urlopen(url)
        return req.getcode(), req.read().decode('utf-8')[:100]
    except Exception as e:
        return 'ERROR', str(e)

print('1. /docs:', check('http://localhost:8080/docs'))
print('2. /api/cases:', check('http://localhost:8080/api/cases'))

cases = ['case_01', 'case_02', 'case_03']
endpoints = ['map', 'spill', 'origin-zone', 'drift', 'vessels', 'candidates']

for c in cases:
    print(f'\\nChecking {c}...')
    print(f'   Base: {check(f"http://localhost:8080/api/cases/{c}")}')
    for ep in endpoints:
        print(f'   {ep}: {check(f"http://localhost:8080/api/cases/{c}/{ep}")}')
