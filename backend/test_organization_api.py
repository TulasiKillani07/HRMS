"""
Quick test script for Organizations API
Run after starting the server: uvicorn app.main:app --reload
"""

import requests
import json

BASE_URL = "http://localhost:8000/HRMS"

def create_superadmin():
    """Create a superadmin user for testing"""
    url = f"{BASE_URL}/auth/register"
    data = {
        "email": "superadmin@hrms.com",
        "password": "SuperAdmin@123",
        "full_name": "Super Admin",
        "role": "superadmin"
    }
    response = requests.post(url, json=data)
    print("✅ Superadmin Created:", response.json() if response.ok else response.text)
    return response.json()

def login_superadmin():
    """Login as superadmin"""
    url = f"{BASE_URL}/auth/login"
    data = {
        "email": "superadmin@hrms.com",
        "password": "SuperAdmin@123"
    }
    response = requests.post(url, json=data)
    if response.ok:
        token_data = response.json()
        print("✅ Login Successful")
        return token_data["access_token"]
    else:
        print("❌ Login Failed:", response.text)
        return None

def create_organization(token):
    """Create a test organization"""
    url = f"{BASE_URL}/organizations/"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "org_name": "Tech Innovations Ltd",
        "email": "contact@techinnovations.com",
        "emp_count_for_access": 50,
        "industry": "Software Development",
        "country": "India",
        "state": "Karnataka",
        "admin_name": "Rajesh Kumar",
        "admin_email": "rajesh@techinnovations.com",
        "admin_phone": "+919876543210",
        "org_address": "123 MG Road, Bangalore"
    }
    response = requests.post(url, json=data, headers=headers)
    print("\n✅ Organization Created:", json.dumps(response.json(), indent=2) if response.ok else response.text)
    return response.json() if response.ok else None

def get_organizations(token):
    """Get all organizations"""
    url = f"{BASE_URL}/organizations/?page=1&limit=10"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    print("\n✅ Organizations List:", json.dumps(response.json(), indent=2) if response.ok else response.text)

def get_organization_by_id(token, org_id):
    """Get organization by ID"""
    url = f"{BASE_URL}/organizations/{org_id}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    print("\n✅ Organization Details:", json.dumps(response.json(), indent=2) if response.ok else response.text)

def update_organization(token, org_id):
    """Update organization"""
    url = f"{BASE_URL}/organizations/{org_id}"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "org_name": "Tech Innovations Pvt Ltd",
        "emp_count_for_access": 75
    }
    response = requests.put(url, json=data, headers=headers)
    print("\n✅ Organization Updated:", json.dumps(response.json(), indent=2) if response.ok else response.text)

def delete_organization(token, org_id):
    """Delete organization"""
    url = f"{BASE_URL}/organizations/{org_id}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(url, headers=headers)
    print("\n✅ Organization Deleted:", json.dumps(response.json(), indent=2) if response.ok else response.text)

if __name__ == "__main__":
    print("=" * 50)
    print("HRMS Organizations API Test")
    print("=" * 50)
    
    # Step 1: Create superadmin
    print("\n[1] Creating Superadmin...")
    create_superadmin()
    
    # Step 2: Login
    print("\n[2] Logging in as Superadmin...")
    token = login_superadmin()
    
    if not token:
        print("❌ Cannot proceed without token")
        exit()
    
    # Step 3: Create organization
    print("\n[3] Creating Organization...")
    org = create_organization(token)
    
    if not org:
        print("❌ Organization creation failed")
        exit()
    
    org_id = org.get("id")
    
    # Step 4: Get all organizations
    print("\n[4] Getting All Organizations...")
    get_organizations(token)
    
    # Step 5: Get organization by ID
    print("\n[5] Getting Organization by ID...")
    get_organization_by_id(token, org_id)
    
    # Step 6: Update organization
    print("\n[6] Updating Organization...")
    update_organization(token, org_id)
    
    # Step 7: Delete organization (soft delete)
    print("\n[7] Deleting Organization (Soft Delete)...")
    delete_organization(token, org_id)
    
    # Step 8: Verify deletion
    print("\n[8] Verifying Organizations List (should not show deleted)...")
    get_organizations(token)
    
    print("\n" + "=" * 50)
    print("✅ All Tests Completed!")
    print("=" * 50)
