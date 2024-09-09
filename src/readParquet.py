#########################################################################
# readParquet.py
# ------------------
# outputting number of articles for each year for a particular school's college 
# newspaper in a specific subject area
# 
# Usage:
#        > python src/readParquet <school> <subject>
#
# where:
#        school  = name of school such as "harvard"
#        subject = section in school newspaper such as "opinion" or "opinions"
#
# @author Theodore Mui
# @email theodoremui@gmail.com
# @date Sun Feb 19 17:37:21 PST 2023
#
# Retry logic: bit.ly/requests-retry
#########################################################################

import argparse
import os
import sys
import pandas as pd
from util.ouraws import (
    getFromFile
)

OUTPUT_DIR="data"

def getStoredArticles(filename):
    return getFromFile(filename, False)

def printResults(filename):
    print(f"reading from {filename}")
    df = getStoredArticles(filename)

    if df.empty:
        print("No articles found.")
    else:
        df = df.sort_values('year')
        print(f"Number of records: {df.shape}")
    
        # Get the earliest article
        earliest = df.sort_values(['year', 'month', 'day']).iloc[0]
        print(f"Earliest: {earliest['year']}-{earliest['month']}-{earliest['day']}")

        # Get the latest article
        latest = df.sort_values(['year', 'month', 'day'], ascending=False).iloc[0]
        print(f"Latest:   {latest['year']}-{latest['month']}-{latest['day']}")

        start_year = df['year'].min()
        end_year = df['year'].max()
        for year in range(start_year, end_year + 1):
            year_df = df[df['year'] == year]
            print(f"{year}\t{year_df.shape[0]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read and analyze Parquet files for college newspaper articles.")
    parser.add_argument("school", help="Name of the school (e.g., 'harvard')")
    parser.add_argument("subject", help="Section in school newspaper (e.g., 'opinion' or 'opinions')")
    args = parser.parse_args()

    try:
        filename = f"{OUTPUT_DIR}/{args.school}-{args.subject}.parquet"
        printResults(filename)
    except Exception as e:
        print(f"Exception: {e}")
