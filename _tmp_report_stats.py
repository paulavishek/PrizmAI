import json
data = json.load(open('spectra_test_results.json', encoding='utf-8'))
times = [d['elapsed_seconds'] for d in data]
sections = {}
for d in data:
    s = d.get('section', 'Unknown')
    if s not in sections:
        sections[s] = {'count': 0, 'times': []}
    sections[s]['count'] += 1
    sections[s]['times'].append(d['elapsed_seconds'])

print('=== SECTION STATS ===')
for s, info in sections.items():
    avg = sum(info['times'])/len(info['times'])
    print(f"  {s}: {info['count']} questions, avg {avg:.1f}s")

print(f"\nOverall: {len(data)} questions, avg {sum(times)/len(times):.1f}s, total {sum(times):.0f}s")
print(f"Min: {min(times):.1f}s, Max: {max(times):.1f}s")

# Count action questions
action_qs = [d for d in data if d.get('is_action_question')]
print(f"\nAction questions: {len(action_qs)}")
print(f"Read-only questions: {len(data) - len(action_qs)}")
