"""
Bulk-import regional centers and technicians into the Job Management API.

USAGE (run from your backend folder, with venv active):
    py import_technicians.py

Requires the 'requests' package (already installed if you ran import_customers.py before).
"""

import csv
import sys
import time

try:
    import requests
except ImportError:
    print("The 'requests' package is not installed. Run: pip install requests --break-system-packages")
    sys.exit(1)

BASE_URL = "https://job-app-backend-4o6f.onrender.com"

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
        response = requests.post(f"{BASE_URL}/regional-centers/", json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            new_id = response.json()["id"]
            name_to_id[name] = new_id
            created += 1
            print(f"  Created regional center '{name}' (id={new_id})")
        elif response.status_code == 500:
            # This deployment occasionally 500s even when the record saved successfully.
            time.sleep(0.5)
            refreshed = requests.get(f"{BASE_URL}/regional-centers/", headers=headers).json()
            match = next((c for c in refreshed if c["name"] == name), None)
            if match:
                name_to_id[name] = match["id"]
                created += 1
                print(f"  Created regional center '{name}' (id={match['id']}) — confirmed after 500")
            else:
                print(f"  FAILED to create '{name}': 500, and not found on double-check")
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
        user_response = requests.post(f"{BASE_URL}/users/", json=user_payload, timeout=30)

        user_id = None
        if user_response.status_code == 200:
            user_id = user_response.json()["id"]
        elif user_response.status_code == 500:
            # Occasional false-500 quirk — check via GET before assuming it failed
            time.sleep(0.5)
            all_users = requests.get(f"{BASE_URL}/users/", headers=headers).json()
            match = next((u for u in all_users if u["phone"] == phone), None)
            if match:
                user_id = match["id"]
                print(f"  User '{name}' created — confirmed after 500")
            else:
                print(f"  Skipped '{name}' — user creation failed (500, not found on double-check)")
                skipped += 1
                continue
        else:
            print(f"  Skipped '{name}' — user creation failed: {user_response.status_code} {user_response.text}")
            skipped += 1
            continue

        # 2. Link them as a technician in their region
        tech_payload = {
            "user_id": user_id,
            "regional_center_id": region_id,
            "is_available": True,
        }
        tech_response = requests.post(f"{BASE_URL}/technicians/", json=tech_payload, headers=headers, timeout=30)

        if tech_response.status_code == 200:
            created += 1
            print(f"  Created technician '{name}' in {region} (phone: {phone})")
        elif tech_response.status_code == 500:
            time.sleep(0.5)
            all_techs = requests.get(f"{BASE_URL}/technicians/", headers=headers).json()
            match = next((t for t in all_techs if t["user_id"] == user_id), None)
            if match:
                created += 1
                print(f"  Created technician '{name}' in {region} (phone: {phone}) — confirmed after 500")
            else:
                failed += 1
                print(f"  FAILED to link '{name}' as technician: 500, and not found on double-check")
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