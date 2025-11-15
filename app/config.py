import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

AZURE_VISION_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT", "")
AZURE_VISION_KEY = os.getenv("AZURE_VISION_KEY", "")
PORT = int(os.getenv("PORT", "8000"))

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")