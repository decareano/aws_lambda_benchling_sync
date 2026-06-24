import json
import boto3
import urllib.request
import urllib.error
from botocore.exceptions import ClientError

# --- CONFIGURATION (Keep your verified AWS settings here) ---
MOCK_MODE = True  # Set to True to test without a Benchling account or Secrets Manager!
SECRET_NAME = "prod/benchling/api_key"  # Put your exact working secret name here
AWS_REGION = "us-east-1"  # Put your exact working region here
BENCHLING_TENANT = (
    "your-company-name"  # Change to your actual Benchling tenant name (e.g., "acme")
)
# ------------------------------------------------------------


def get_secret():
    """Fetches the secure API token from AWS Secrets Manager."""
    if MOCK_MODE:
        print("[MOCK MODE ACTIVE] Bypassing Secrets Manager. Returning mock token.")
        return "mock-benchling-token-12345"

    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=AWS_REGION)

    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
        secret_dict = json.loads(response["SecretString"])
        return secret_dict["BENCHLING_TOKEN"]
    except ClientError as e:
        print(f"Error retrieving secret: {e}")
        raise e


def run_matching_engine(incoming_data, credentials):
    """Fetches live Benchling inventory using credentials and filters incoming samples."""

    if MOCK_MODE:
        print("[MOCK MODE ACTIVE] Bypassing live API request to Benchling.")
        # This simulates what Benchling's API would return
        live_benchling_data = {
            "entries": [{"name": "plasmid_v1"}, {"name": "crispr_buffer_a"}]
        }
    else:
        # Benchling API endpoints are tenant-specific: https://<tenant>.benchling.com/api/v2/entries
        url = f"https://{BENCHLING_TENANT}.benchling.com/api/v2/entries"

        # 1. Fetch live registry data from Benchling API using native urllib
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {credentials}")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req) as response:
                response_body = response.read().decode("utf-8")
                live_benchling_data = json.loads(response_body)
        except urllib.error.URLError as e:
            print(f"Error fetching data from Benchling API: {e}")
            raise e

    # Parse out registry entry names to compare against
    benchling_inventory = set()
    if isinstance(live_benchling_data, dict) and "entries" in live_benchling_data:
        for entry in live_benchling_data["entries"]:
            name = entry.get("name")
            if name:
                benchling_inventory.add(name.strip().lower())
    else:
        # Fallback parsing in case of flat dictionary structure
        benchling_inventory = {
            str(k).strip().lower() for k in live_benchling_data.keys()
        }

    # 2. Run the cleaning and matching logic
    new_samples = []
    for each_sample in incoming_data:
        if each_sample is None:
            print("Warning: Found a blank row! Skipping...")
            continue

        clean_sample = each_sample.strip().lower()

        if clean_sample in benchling_inventory:
            print(f"{each_sample} already in inventory. No need to create dups")
        else:
            print(f"{each_sample} is a new sample. We are adding it")
            new_samples.append(clean_sample)

    return new_samples


def lambda_handler(event, context):
    # calling get_secret to retrieve creds
    credentials = get_secret()
    incoming_data = event["data"]
    # describing that we are passing the data and credentials into the matching engine
    engine_results = run_matching_engine(incoming_data, credentials)
    return {"statusCode": 200, "body": engine_results}
    # stating that we are returning final response
