#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:5000/api"

# Login
login_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": "as", "password": "as"}
)

if login_response.status_code == 200:
    login_data = login_response.json()
    token = login_data.get('access_token')
    
    # Get appointments
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(
        f"{BASE_URL}/doctor/appointments",
        headers=headers
    )
    
    print("Status:", response.status_code)
    print("Response type:", type(response.json()))
    print("Full response:")
    print(json.dumps(response.json(), indent=2)[:1000])
else:
    print("Login failed:", login_response.status_code)
