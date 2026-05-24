import json
from pathlib import Path

data = json.loads(Path("knowledge_base/questions.json").read_text(encoding="utf-8"))
red = sum(1 for q in data if q.get("answer_from_red"))
print("total", len(data), "red", red)
for n in [3, 11, 12, 50, 100]:
    q = next((x for x in data if x["number"] == n), None)
    if not q:
        print(n, "MISSING")
        continue
    print(f"Q{n} red={q.get('answer_from_red')} ans={q['answer']}")
