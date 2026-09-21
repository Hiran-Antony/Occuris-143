import sys
sys.stdout.reconfigure(encoding='utf-8')
with open(r'C:\Users\A.visal\OneDrive\Desktop\sih official\app.js', encoding='utf-8', errors='ignore') as f:
    text = f.read()

for i, line in enumerate(text.splitlines()[50:120]):
    print(f"{i+51}: {line}")
