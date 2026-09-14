"""
Bulk-import customers from customers_import.csv into the Job Management API.

USAGE (run from your backend folder, with venv active):
    py import_customers.py

Requires the 'requests' package:
    pip install requests --break-system-packages   (or just: pip install requests)
"""

import csv
import sys
import time

try:
    import requests
except ImportError:
    print("The 'requests' package is not installed. Run: pip install requests")
    sys.exit(1)

BASE_URL = "https://job-app-backend-4o6f.onrender.com"  # your live deployed backend

# --- Log in as a sales executive or admin (needed to create customers) ---
LOGIN_PHONE = "0771234567"   # <-- change to your real sales exec / admin phone
LOGIN_PASSWORD = "test1234"  # <-- change to the matching password

CSV_FILE = "customers_import.csv"


def login():
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": LOGIN_PHONE, "password": LOGIN_PASSWORD},
    )
    if response.status_code != 200:
        print("Login failed:", response.status_code, response.text)
        sys.exit(1)
    return response.json()["access_token"]


def already_exists(name, headers):
    """Double-check via GET, since this deployment occasionally returns a false
    500 on POST even though the record was actually created successfully."""
    try:
        response = requests.get(f"{BASE_URL}/customers/", headers=headers)
        if response.status_code == 200:
            return any(c["name"] == name for c in response.json())
    except requests.exceptions.RequestException:
        pass
    return False


def main():
    token = login()
    headers = {"Authorization": f"Bearer {token}"}

    created = 0
    skipped = 0
    failed = 0
    review_needed = []

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Importing {len(rows)} customers...\n")

    for i, row in enumerate(rows, start=1):
        name = row["name"].strip()
        address = row["original_location"].strip()
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        needs_review = row["needs_review"].strip().lower() == "true"

        payload = {
            "name": name,
            "address": address,
            "latitude": lat,
            "longitude": lon,
        }

        try:
            response = requests.post(f"{BASE_URL}/customers/", json=payload, headers=headers, timeout=30)
        except requests.exceptions.ConnectionError:
            print("Could not reach the backend. Check the URL and that it's awake.")
            sys.exit(1)

        if response.status_code == 200:
            created += 1
            if needs_review:
                review_needed.append(name)
            if i % 20 == 0 or i == len(rows):
                print(f"  {i}/{len(rows)} processed...")
        elif response.status_code == 422:
            skipped += 1
            print(f"  Skipped '{name}' — validation error: {response.json()}")
        elif response.status_code == 500:
            # This deployment occasionally 500s even when the record saved successfully.
            # Double-check via GET before concluding it actually failed.
            time.sleep(0.5)
            if already_exists(name, headers):
                created += 1
                if needs_review:
                    review_needed.append(name)
            else:
                failed += 1
                print(f"  Failed '{name}' — 500, and not found on double-check")
        else:
            failed += 1
            print(f"  Failed '{name}' — {response.status_code}: {response.text}")

    print("\nDone.")
    print(f"  Created: {created}")
    print(f"  Skipped (validation): {skipped}")
    print(f"  Failed: {failed}")
    if review_needed:
        print(f"\n  These {len(review_needed)} customer(s) used a placeholder location")
        print("  (Colombo coordinates) and should be corrected manually once you know")
        print("  their real site location:")
        for name in set(review_needed):
            print(f"    - {name}")


if __name__ == "__main__":
    main()