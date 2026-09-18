import json

with open("openapi_dump.json", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total paths: {len(data.get('paths', {}))}")
paths = data.get('paths', {})
for path in sorted(paths.keys()):
    methods = paths[path]
    for m in ['get', 'post', 'put', 'patch', 'delete']:
        if m in methods:
            details = methods[m]
            tags = details.get('tags', [])
            tag = tags[0] if tags else 'General'
            print(f"{m.upper():<6} {path:<45} [{tag}] {details.get('summary', '')}")
