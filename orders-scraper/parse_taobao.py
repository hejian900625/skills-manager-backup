import pandas as pd

# Read HTML file
with open('taobao_2023-08-03.html', 'r', encoding = 'utf-8') as f:
    contents = f.read()

# Use pandas to find tables in the HTML
tables = pd.read_html(contents)

# Extract column names from the first table
column_names = tables[0].iloc[0]

# Concatenate the remaining tables vertically, using the column names from the first table
df = pd.concat([df.rename(columns=column_names) for df in tables[1:]], ignore_index=True)

df.to_excel("output.xlsx")
print(tables[0])
print(tables[1])
print(tables[2])