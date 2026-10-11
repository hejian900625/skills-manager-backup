import pandas as pd

# Read HTML file
with open('jingdong_2023-08-03.html', 'r', encoding = 'utf-8') as f:
    contents = f.read()

# Use pandas to find tables in the HTML
tables = pd.read_html(contents)

# Concatenate the remaining tables vertically, using the column names from the first table
df = pd.concat(tables, ignore_index=True)
df = df.drop("收货人", axis=1)
df.to_excel("output.xlsx")
print(tables[0])
print(tables[1])
print(tables[2])