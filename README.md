# Diversity Colleges Project
```
Author: Theodore Mui
Email: theodoremui@gmail.com
```
We are glad that you are here!


In this project, we use web scraping and natural language processing to measure the diversity of ideas in colleges. We want to determine whether there is a relationship between the diversity of ideas and the size or prestige of the college. We scrape the opinion section of college newspapers and use word vectors to calculate the similarity between words. 

## Usage

An example usage of the project is shown below.

```
# assume that you are at the toplevel of the project
# we would like to crawl the opinion section of the college newspapers from UT Austin, 
# pages 1 - 386, and save the results in ./data

unbuffer python ./src/crawl2parquet.py ./config/brown-opinions.yaml 1 237 2>&1 | tee -a logs/brown-opinions-0901.log

```

## Development

For developers, frontend installation is fairly staightfoward from the toplevel of the project (here)

```
pip install poetry
poetry config virtualenvs.in-project true
poetry install --no-root
poetry shell

```
