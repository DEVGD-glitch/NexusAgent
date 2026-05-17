import sys
from pathlib import Path

report = Path('graphify-out/GRAPH_REPORT.md').read_text(encoding='utf-8')

sections = ['God Nodes', 'Surprising Connections', 'Suggested Questions']
for s in sections:
    idx = report.find(f'## {s}')
    if idx >= 0:
        end = report.find('## ', idx + 3)
        if end < 0:
            end = len(report)
        print(report[idx:end].strip().encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        print()
