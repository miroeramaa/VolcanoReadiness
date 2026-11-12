import pandas as pd
import matplotlib.pyplot as plt

##NOTE THAT VOLCANOES ARE NOT MATCHED BY COORDINATES 

# change these to your real file names
volcano_file = "data/volcano_summary.csv"
population_file = "data/kontur_10km_population_scores.csv"

volcanoes = pd.read_csv(volcano_file)
population = pd.read_csv(population_file)

# only keep the columns we need, otherwise the merge gets messy
# (both files have name, lat, lon...)
volcanoes = volcanoes[["name", "volcano_number", "readiness", "houses"]]
population = population[["gvp_volcano_number", "population_on_10km",
                         "kontur_geometry_coverage_pct"]]

# gvp_volcano_number is a float (263130.0) and sometimes empty,
# so drop the empty ones and make it a normal integer
population = population.dropna(subset=["gvp_volcano_number"])
population = population.astype({"gvp_volcano_number": int})

# in case a volcano shows up more than once
population = population.drop_duplicates(subset="gvp_volcano_number")

# put the two tables together using the volcano number
data = volcanoes.merge(population,
                       left_on="volcano_number",
                       right_on="gvp_volcano_number")

print(len(data), "volcanoes matched")

# print volcanoes with population below 100 and more than 1000 houses
matching_volcanoes = data[data["houses"] > data["population_on_10km"]]
for name in matching_volcanoes["name"]:
    print(name)

# two plots next to each other
fig, ax1 = plt.subplots(1, 1, figsize=(12, 5))

# plot 1: population within 10 km vs houses
ax1.scatter(data["population_on_10km"], data["houses"])
ax1.set_xscale("log")  # population is very spread out, remove this line if you don't like it
ax1.set_yscale("log")
ax1.set_xlabel("population_on_10km")
ax1.set_ylabel("houses")
ax1.set_title("Population vs houses")

"""# plot 2: invalid population hexagons vs readiness
ax2.scatter(data["kontur_geometry_coverage_pct"], data["readiness"])
ax2.set_xlabel("kontur_geometry_coverage_pct")
ax2.set_ylabel("readiness")
ax2.set_title("geometry coverage vs readiness")"""



print()

plt.tight_layout()
plt.savefig("scatter.png", dpi=150)
plt.show()