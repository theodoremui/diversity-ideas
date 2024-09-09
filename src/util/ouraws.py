#########################################################################
#
# ouraws.py
#
# @author Theodore Mui
# @email theodoremui@gmail.com
# @date Sun Feb 12 16:34:09 PST 2023
#
#########################################################################

import io
import os
import pandas as pd

import boto3
import botocore
import pyarrow as pa
import pyarrow.parquet as pq

S3_BUCKET="research-colleges"
s3 = boto3.client('s3')

def getFromS3(s3object_key: str) -> pd.DataFrame:
    df = None
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=s3object_key)
        df = pd.read_parquet(io.BytesIO(response['Body'].read()))
        # s3.download_file(S3_BUCKET, s3object_key, s3object_key)
        # df = pd.read_parquet(s3object_key)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"\tgetFromS3(): Object not found: {s3object_key}. Creating an empty DataFrame.")
            df = pd.DataFrame()
            s3.put_object(Bucket=S3_BUCKET, Key=s3object_key, Body=b'')
        else:
            print(f"\tgetFromS3(): Error accessing object: {s3object_key}")
            raise e
    return df

def getFromFile(file_path: str, create_if_not_exist: bool=True) -> pd.DataFrame:
    """
    Read a parquet file from a local directory. If the file doesn't exist,
    create an empty file and return an empty DataFrame.

    Args:
    file_path (str): The full path to the parquet file.

    Returns:
    pd.DataFrame: The DataFrame read from the file, or an empty DataFrame if the file didn't exist.
    """
    try:
        # Check if the file exists
        if os.path.exists(file_path):
            # If it exists, read the parquet file
            df = pd.read_parquet(file_path)
        else:
            df = pd.DataFrame()
            if create_if_not_exist:
                directory = os.path.dirname(file_path)
                os.makedirs(directory, exist_ok=True)
                df.to_parquet(file_path, engine='pyarrow')
        
        return df
    
    except Exception as e:
        print(f"Error accessing file: {file_path}")
        print(f"Error details: {str(e)}")
        # In case of any error, return an empty DataFrame
        return pd.DataFrame()

def putToS3(s3object_key, df):
    buffer = io.BytesIO()
    df.to_parquet(buffer, engine='pyarrow')
    buffer.seek(0)
    s3.put_object(Bucket=S3_BUCKET, Key=s3object_key, Body=buffer.getvalue())
    
    # Save the dataframe to a local parquet file
    # df.to_parquet('df.parquet', engine='pyarrow')
    # s3.upload_file('df.parquet', S3_BUCKET, s3object_key)

def putToFile(file_path: str, df: pd.DataFrame):
    """
    Save a DataFrame to a local parquet file. If the file exists, override.
    If the directory doesn't exist, create it.

    Args:
    file_path (str): The full path to the parquet file.
    df (pd.DataFrame): The DataFrame to save.

    Returns:
    pd.DataFrame: the saved DataFrame
    """
    # Ensure the directory exists
    directory = os.path.dirname(file_path)
    os.makedirs(directory, exist_ok=True)

    # Save the combined DataFrame to the parquet file
    df.to_parquet(file_path, engine='pyarrow', index=False)


def saveNewArticles(new_articles: list[dict], checkpoint_name: str):
    new_df = pd.DataFrame.from_records(new_articles)
    # stored_df = getFromS3(checkpoint_name)
    stored_df = getFromFile(checkpoint_name)
    if stored_df is None or stored_df.size == 0:
        stored_df = new_df
    else:
        stored_df = stored_df[~ stored_df['url'].isin(new_df['url'])]
        stored_df = pd.concat([stored_df, new_df])

    print(f"\t{checkpoint_name}: {stored_df.shape} articles")
    # putToS3(checkpoint_name, stored_df)
    putToFile(checkpoint_name, stored_df)
    return stored_df

def saveByYear(df: pd.DataFrame, output_dir: str, prefix: str):
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    oldest_year = df['year'].min()
    latest_year = df['year'].max()

    for y in range(oldest_year, latest_year+1):
        print(f"{y} has {df[df.year == y].shape[0]} articles")
        putToFile(f"{output_dir}/{prefix}-{y}.parquet", df[df.year == y])


def saveBipartisanResults(
    new_results: list[dict], 
    primary_key: str, 
    output_name: str
) -> pd.DataFrame:
    
    new_df = pd.DataFrame.from_records(new_results)
    # stored_df = getFromS3(output_name)
    stored_df = getFromFile(output_name)
    if stored_df is None or stored_df.size == 0:
        stored_df = new_df
    else:
        stored_df = stored_df[~ stored_df[primary_key].isin(new_df[primary_key])]
        stored_df = pd.concat([stored_df, new_df])

    print(f"\t{output_name}: {stored_df.shape}")
    # putToS3(output_name, stored_df)
    putToFile(output_name, stored_df)
    return stored_df