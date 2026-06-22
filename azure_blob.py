import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

# Extract and clean connection string
connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
if connection_string:
    connection_string = connection_string.strip('"\'')

container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "ask-evaa")
if container_name:
    container_name = container_name.strip('"\'')

if not connection_string:
    raise ValueError("AZURE_STORAGE_CONNECTION_STRING is not set in environment.")

blob_service_client = BlobServiceClient.from_connection_string(connection_string)

def upload_to_blob(file_path: str, blob_name: str) -> str:
    """Uploads a local file to Azure Blob Storage and returns its URL."""
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    with open(file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)
    return blob_client.url

def download_from_blob(blob_name: str, download_path: str):
    """Downloads a blob from Azure Blob Storage to a local path."""
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    with open(download_path, "wb") as download_file:
        download_file.write(blob_client.download_blob().readall())

def delete_blob(blob_name: str):
    """Deletes a blob from Azure Blob Storage."""
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    blob_client.delete_blob()
