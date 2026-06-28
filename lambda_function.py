import json
import boto3
import urllib.request
import urllib.error
import re
from botocore.exceptions import ClientError

# --- CONFIGURATION (Your verified AWS settings) ---
MOCK_MODE = True  # Set to True to test without a Benchling account or Secrets Manager!
SECRET_NAME = "prod/benchling/api_key"
AWS_REGION = "us-east-1"
BENCHLING_TENANT = "your-company-name"
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


def validate_samples(incoming_data):
    """
    CHALLENGE 1: Validates sample names.
    Returns: (list of valid samples, count of invalid rows, count of blank rows)
    """
    valid_samples = []
    invalid_rows = 0
    blank_rows = 0

    for each_item in incoming_data:
        # Track blank rows
        if each_item is None or (isinstance(each_item, str) and not each_item.strip()):
            blank_rows += 1
            print("Warning: Found a blank row! Skipping...")
            continue

        # Track invalid rows (type checks)
        if not isinstance(each_item, str):
            invalid_rows += 1
            print(f"Warning: Rejected item {each_item} (Invalid type)")
            continue

        cleaned_item = each_item.strip()

        # Track invalid rows (length constraints)
        if not (5 <= len(cleaned_item) <= 50):
            invalid_rows += 1
            print(f"Warning: Rejected {cleaned_item} (Length out of bounds)")
            continue

        # Track invalid rows (regex pattern constraints)
        if not re.match("^(plasmid_|crispr_|compound_)[a-zA-Z0-9_]*$", cleaned_item):
            invalid_rows += 1
            print(f"Warning: Rejected {cleaned_item} (Failed naming convention)")
            continue

        valid_samples.append(cleaned_item)

    return valid_samples, invalid_rows, blank_rows


def generate_summary(total, blanks, invalids, duplicates, new_samples):
    """
    CHALLENGE 2: The Metrics & Telemetry Engine.
    Generates a structured dictionary summarizing execution metadata.
    """
    return {
        "total_received": total,
        "blank_rows": blanks,
        "invalid_rows": invalids,
        "duplicates_found": duplicates,
        "new_samples_identified": new_samples,
    }


def run_matching_engine(incoming_data, credentials):
    """
    Fetches live Benchling inventory using credentials, runs
    Challenge 1 validation, metrics collection, and filters duplicates.
    """
    # 1. Gather baseline total metrics
    total_received = len(incoming_data)

    # 2. CHALLENGE 1 INTEGRATION: Validate inputs first and extract structural metrics
    valid_inputs, invalid_rows, blank_rows = validate_samples(incoming_data)

    if MOCK_MODE:
        print("[MOCK MODE ACTIVE] Bypassing live API request to Benchling.")
        live_benchling_data = {
            "entries": [{"name": "plasmid_v1"}, {"name": "crispr_buffer_a"}]
        }
    else:
        url = f"https://{BENCHLING_TENANT}.benchling.com/api/v2/entries"
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
        benchling_inventory = {
            str(k).strip().lower() for k in live_benchling_data.keys()
        }

    # 3. Process remaining clean, valid data through duplicate tracking logic
    new_samples = []
    duplicates_found = 0

    for each_sample in valid_inputs:
        clean_sample = each_sample.lower()

        if clean_sample in benchling_inventory:
            print(f"{each_sample} already in inventory. No need to create dups")
            duplicates_found += 1
        else:
            print(f"{each_sample} is a new sample. We are adding it")
            new_samples.append(clean_sample)

    # 4. CHALLENGE 2 INTEGRATION: Build telemetry summary payload
    metrics_summary = generate_summary(
        total=total_received,
        blanks=blank_rows,
        invalids=invalid_rows,
        duplicates=duplicates_found,
        new_samples=len(new_samples),
    )

    return new_samples, metrics_summary


def lambda_handler(event, context):
    try:
        credentials = get_secret()
        incoming_data = event.get("data", [])

        # Pass the data and credentials into our updated matching engine
        engine_results, metrics = run_matching_engine(incoming_data, credentials)

        # Return a structured response that contains both our telemetry and results
        return {
            "statusCode": 200,
            "body": {"new_samples": engine_results, "metrics": metrics},
        }
    except Exception as e:
        return {"statusCode": 500, "body": f"Error executing pipeline: {str(e)}"}
