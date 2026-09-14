"""
Bulk-import regional centers and technicians into the Job Management API.

USAGE (run from your backend folder, with venv active and the server running):
    py import_technicians.py

Requires the 'requests' package (already installed if you ran import_customers.py before).
"""

import csv
import sys

try:
    import requests
except ImportError:
    print("The 'requests' package is not installed. Run: pip install requests --break-system-packages")
    sys.exit(1)

BASE_URL = "http://localhost:8000"

# --- Log in as ADMIN (required to create regional centers and technicians) ---
LOGIN_PHONE = "0700000001"    # <-- change to your real admin phone
LOGIN_PASSWORD = "admin1234"  # <-- change to the matching password

CENTERS_CSV = "regional_centers_import.csv"
TECHS_CSV = "technicians_import.csv"


def login():
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": LOGIN_PHONE, "password": LOGIN_PASSWORD},
    )
    if response.status_code != 200:
        print("Login failed:", response.status_code, response.text)
        sys.exit(1)
    return response.json()["access_token"]


def get_or_create_regional_centers(headers):
    """Returns a dict: region name -> regional_center_id, creating any that don't already exist."""
    existing = requests.get(f"{BASE_URL}/regional-centers/", headers=headers).json()
    name_to_id = {c["name"]: c["id"] for c in existing}

    with open(CENTERS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    created = 0
    for row in rows:
        name = row["name"].strip()
        if name in name_to_id:
            print(f"  Regional center '{name}' already exists (id={name_to_id[name]}) — skipping")
            continue
        payload = {
            "name": name,
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
        }
        response = requests.post(f"{BASE_URL}/regional-centers/", json=payload, headers=headers)
        if response.status_code == 200:
            new_id = response.json()["id"]
            name_to_id[name] = new_id
            created += 1
            print(f"  Created regional center '{name}' (id={new_id})")
        else:
            print(f"  FAILED to create '{name}': {response.status_code} {response.text}")

    print(f"\nRegional centers: {created} created, {len(name_to_id)} total available.\n")
    return name_to_id


def import_technicians(headers, region_map):
    with open(TECHS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    created = 0
    skipped = 0
    failed = 0

    for row in rows:
        name = row["name"].strip()
        phone = row["phone"].strip()
        email = row["email"].strip()
        password = row["password"].strip()
        region = row["region"].strip()

        region_id = region_map.get(region)
        if not region_id:
            print(f"  Skipped '{name}' — unknown region '{region}'")
            skipped += 1
            continue

        # 1. Create the user account (signup is open, no auth needed)
        user_payload = {
            "name": name,
            "phone": phone,
            "email": email,
            "password": password,
            "role": "technician",
        }
        user_response = requests.post(f"{BASE_URL}/users/", json=user_payload)

        if user_response.status_code != 200:
            print(f"  Skipped '{name}' — user creation failed: {user_response.status_code} {user_response.text}")
            skipped += 1
            continue

        user_id = user_response.json()["id"]

        # 2. Link them as a technician in their region
        tech_payload = {
            "user_id": user_id,
            "regional_center_id": region_id,
            "is_available": True,
        }
        tech_response = requests.post(f"{BASE_URL}/technicians/", json=tech_payload, headers=headers)

        if tech_response.status_code == 200:
            created += 1
            print(f"  Created technician '{name}' in {region} (phone: {phone})")
        else:
            failed += 1
            print(f"  FAILED to link '{name}' as technician: {tech_response.status_code} {tech_response.text}")

    print(f"\nTechnicians: {created} created, {skipped} skipped, {failed} failed.")


def main():
    token = login()
    headers = {"Authorization": f"Bearer {token}"}

    print("Step 1: Regional centers\n" + "-" * 40)
    region_map = get_or_create_regional_centers(headers)

    print("Step 2: Technicians\n" + "-" * 40)
    import_technicians(headers, region_map)


if __name__ == "__main__":
    main()
