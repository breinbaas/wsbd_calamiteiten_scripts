# haalt dubbele regels uit results.csv
lines = open("./output/results.csv", "r").readlines()

result = []
for line in lines:
    if not line in result:
        result.append(line)

with open("./output/results_cleared.csv", "w") as f:
    for line in result:
        f.write(line)
