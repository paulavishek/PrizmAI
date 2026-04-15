import os

path = r'c:\Users\Avishek Paul\PrizmAI\templates\kanban\coach_dashboard.html'
with open(path, 'rb') as f:
    data = f.read()

idx = data.find(b'Proactive')
if idx >= 0:
    segment = data[idx-30:idx+50]
    print("Raw bytes:", segment)
    print("Hex:", segment.hex())
    print("Repr:", repr(segment))
else:
    print("'Proactive' not found")

# Also search for various encoding patterns
patterns = {
    'utf8-emdash': b'\xe2\x80\x94',
    'double-encoded': b'\xc3\xa2\xc2\x80\xc2\x94',
    'cp1252-emdash': b'\x97',
    'win-endash': b'\x96',
}
for name, pat in patterns.items():
    c = data.count(pat)
    if c:
        print(f"{name}: {c} occurrences")
