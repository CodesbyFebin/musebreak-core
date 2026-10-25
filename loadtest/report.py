import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
print("| endpoint | reqs | fails | RPS | p50 ms | p95 ms | p99 ms |\n|---|---|---|---|---|---|---|")
for r in rows:
    print(f"| {r['Name']} | {r['Request Count']} | {r['Failure Count']} | {float(r['Requests/s']):.1f} | "
          f"{r['50%']} | {r['95%']} | {r['99%']} |")
