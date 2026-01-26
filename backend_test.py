#!/usr/bin/env python3
"""
RFID Cloud API Backend Testing
Tests all endpoints including admin and device authentication flows
"""
import requests
import sys
import json
import hashlib
from datetime import datetime
from typing import Optional

class RFIDAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.admin_api_key = "change-this-admin-key-in-production"
        self.device_token = None
        self.device_id = None
        self.mac_address = "D8:3A:DD:B3:E0:7F"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        
        result = f"{status} - {name}"
        if details:
            result += f" | {details}"
        
        print(result)
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details
        })
        return success

    def make_request(self, method: str, endpoint: str, expected_status: int = 200, 
                    data: dict = None, headers: dict = None, admin_auth: bool = False,
                    device_auth: bool = False) -> tuple[bool, dict]:
        """Make HTTP request with proper authentication"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Setup headers
        req_headers = {'Content-Type': 'application/json'}
        if headers:
            req_headers.update(headers)
        
        # Add authentication
        if admin_auth:
            req_headers['X-Admin-API-Key'] = self.admin_api_key
        elif device_auth and self.device_token:
            req_headers['Authorization'] = f'Bearer {self.device_token}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=req_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=req_headers)
            else:
                return False, {"error": f"Unsupported method: {method}"}

            success = response.status_code == expected_status
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text, "status_code": response.status_code}
            
            return success, response_data

        except Exception as e:
            return False, {"error": str(e)}

    def generate_device_id(self, mac_address: str) -> str:
        """Generate device ID same way as server"""
        return hashlib.sha256(f"rfid-device-{mac_address}".encode()).hexdigest()[:16]

    def test_health_check(self):
        """Test health check endpoint"""
        success, response = self.make_request('GET', '/health')
        if success and response.get('status') in ['healthy', 'degraded']:
            return self.log_test("Health Check", True, f"Status: {response.get('status')}")
        return self.log_test("Health Check", False, f"Response: {response}")

    def test_root_endpoint(self):
        """Test root endpoint"""
        success, response = self.make_request('GET', '/')
        if success and response.get('service') == 'RFID Cloud API':
            return self.log_test("Root Endpoint", True, f"Version: {response.get('version')}")
        return self.log_test("Root Endpoint", False, f"Response: {response}")

    def test_admin_register_device(self):
        """Test device registration (admin endpoint)"""
        # First check if device already exists
        expected_id = self.generate_device_id(self.mac_address)
        existing_success, existing_response = self.make_request(
            'GET', f'/api/admin/devices/{expected_id}', admin_auth=True
        )
        
        if existing_success:
            # Device already exists, use it
            self.device_id = expected_id
            return self.log_test("Admin Register Device", True, f"Device already exists: {self.device_id}")
        
        # Device doesn't exist, try to register it
        device_data = {
            "mac_address": self.mac_address,
            "device_name": "Test RFID Reader",
            "location": "Test Lab"
        }
        
        success, response = self.make_request(
            'POST', '/api/admin/devices/register', 
            expected_status=200, data=device_data, admin_auth=True
        )
        
        if success and response.get('device_id'):
            self.device_id = response['device_id']
            if self.device_id == expected_id:
                return self.log_test("Admin Register Device", True, f"New device registered: {self.device_id}")
            else:
                return self.log_test("Admin Register Device", False, f"ID mismatch: got {self.device_id}, expected {expected_id}")
        
        # If registration failed due to duplicate, try to get the existing device
        if response.get('detail') and 'already registered' in response['detail'].lower():
            self.device_id = expected_id
            return self.log_test("Admin Register Device", True, f"Device exists (duplicate): {self.device_id}")
        
        return self.log_test("Admin Register Device", False, f"Response: {response}")

    def test_admin_register_duplicate(self):
        """Test registering duplicate device (should fail)"""
        device_data = {
            "mac_address": self.mac_address,
            "device_name": "Duplicate Device",
            "location": "Test Lab"
        }
        
        success, response = self.make_request(
            'POST', '/api/admin/devices/register', 
            expected_status=400, data=device_data, admin_auth=True
        )
        
        if success and 'already registered' in response.get('detail', '').lower():
            return self.log_test("Admin Register Duplicate", True, "Correctly rejected duplicate")
        return self.log_test("Admin Register Duplicate", False, f"Response: {response}")

    def test_admin_list_devices(self):
        """Test listing devices (admin endpoint)"""
        success, response = self.make_request('GET', '/api/admin/devices', admin_auth=True)
        
        if success and isinstance(response, list):
            device_found = any(d.get('device_id') == self.device_id for d in response)
            if device_found:
                return self.log_test("Admin List Devices", True, f"Found {len(response)} devices")
            else:
                return self.log_test("Admin List Devices", False, "Registered device not found in list")
        
        return self.log_test("Admin List Devices", False, f"Response: {response}")

    def test_admin_get_device(self):
        """Test getting specific device (admin endpoint)"""
        if not self.device_id:
            return self.log_test("Admin Get Device", False, "No device_id available")
        
        success, response = self.make_request(
            'GET', f'/api/admin/devices/{self.device_id}', admin_auth=True
        )
        
        if success and response.get('device_id') == self.device_id:
            return self.log_test("Admin Get Device", True, f"Status: {response.get('status')}")
        return self.log_test("Admin Get Device", False, f"Response: {response}")

    def test_admin_statistics(self):
        """Test getting system statistics (admin endpoint)"""
        success, response = self.make_request('GET', '/api/admin/statistics', admin_auth=True)
        
        if success and 'devices' in response and 'readings' in response:
            devices = response['devices']
            readings = response['readings']
            return self.log_test("Admin Statistics", True, 
                               f"Devices: {devices.get('total')}, Readings: {readings.get('total')}")
        
        return self.log_test("Admin Statistics", False, f"Response: {response}")

    def test_device_authenticate(self):
        """Test device authentication"""
        if not self.device_id:
            return self.log_test("Device Authentication", False, "No device_id available")
        
        auth_data = {
            "device_id": self.device_id,
            "mac_address": self.mac_address
        }
        
        success, response = self.make_request(
            'POST', '/api/devices/authenticate', 
            expected_status=200, data=auth_data
        )
        
        if success and response.get('access_token'):
            self.device_token = response['access_token']
            return self.log_test("Device Authentication", True, 
                               f"Token expires in: {response.get('expires_in')}s")
        
        return self.log_test("Device Authentication", False, f"Response: {response}")

    def test_device_authenticate_invalid(self):
        """Test device authentication with invalid credentials"""
        auth_data = {
            "device_id": "invalid_device_id",
            "mac_address": "00:00:00:00:00:00"
        }
        
        success, response = self.make_request(
            'POST', '/api/devices/authenticate', 
            expected_status=401, data=auth_data
        )
        
        if success and 'not registered' in response.get('detail', '').lower():
            return self.log_test("Device Auth Invalid", True, "Correctly rejected invalid device")
        return self.log_test("Device Auth Invalid", False, f"Response: {response}")

    def test_get_config(self):
        """Test getting device configuration"""
        if not self.device_token:
            return self.log_test("Get Config", False, "No device token available")
        
        success, response = self.make_request('GET', '/api/config', device_auth=True)
        
        if success and 'rabbitmq_host' in response:
            return self.log_test("Get Config", True, 
                               f"RabbitMQ: {response.get('rabbitmq_host')}:{response.get('rabbitmq_port')}")
        
        return self.log_test("Get Config", False, f"Response: {response}")

    def test_submit_readings(self):
        """Test submitting RFID readings"""
        if not self.device_token or not self.device_id:
            return self.log_test("Submit Readings", False, "No device token or ID available")
        
        readings_data = {
            "readings": [
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "device_id": self.device_id,
                    "mac_address": self.mac_address,
                    "epc": "E200001234567890",
                    "antenna": 1,
                    "rssi": -45.5
                },
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "device_id": self.device_id,
                    "mac_address": self.mac_address,
                    "epc": "E200009876543210",
                    "antenna": 2,
                    "rssi": -52.3
                }
            ]
        }
        
        success, response = self.make_request(
            'POST', '/api/readings', 
            expected_status=200, data=readings_data, device_auth=True
        )
        
        if success and response.get('status') == 'ok':
            return self.log_test("Submit Readings", True, f"Received: {response.get('received')} readings")
        
        return self.log_test("Submit Readings", False, f"Response: {response}")

    def test_query_readings(self):
        """Test querying RFID readings"""
        if not self.device_token:
            return self.log_test("Query Readings", False, "No device token available")
        
        success, response = self.make_request('GET', '/api/readings?limit=10', device_auth=True)
        
        if success and 'readings' in response:
            return self.log_test("Query Readings", True, f"Found: {response.get('count')} readings")
        
        return self.log_test("Query Readings", False, f"Response: {response}")

    def test_heartbeat(self):
        """Test device heartbeat"""
        if not self.device_token or not self.device_id:
            return self.log_test("Device Heartbeat", False, "No device token or ID available")
        
        heartbeat_data = {
            "device_id": self.device_id,
            "status": "online",
            "cpu_temp": 52.3,
            "memory_usage": 45.2,
            "disk_usage": 23.1,
            "uptime": 86400
        }
        
        success, response = self.make_request(
            'POST', '/api/heartbeat', 
            expected_status=200, data=heartbeat_data, device_auth=True
        )
        
        if success and response.get('status') == 'ok':
            return self.log_test("Device Heartbeat", True, f"Timestamp: {response.get('timestamp')}")
        
        return self.log_test("Device Heartbeat", False, f"Response: {response}")

    def test_admin_revoke_device(self):
        """Test revoking device access"""
        if not self.device_id:
            return self.log_test("Admin Revoke Device", False, "No device_id available")
        
        success, response = self.make_request(
            'POST', f'/api/admin/devices/{self.device_id}/revoke', 
            expected_status=200, admin_auth=True
        )
        
        if success and response.get('status') == 'revoked':
            return self.log_test("Admin Revoke Device", True, f"Device {self.device_id} revoked")
        
        return self.log_test("Admin Revoke Device", False, f"Response: {response}")

    def test_device_auth_after_revoke(self):
        """Test device authentication after revocation (should fail)"""
        if not self.device_id:
            return self.log_test("Auth After Revoke", False, "No device_id available")
        
        auth_data = {
            "device_id": self.device_id,
            "mac_address": self.mac_address
        }
        
        success, response = self.make_request(
            'POST', '/api/devices/authenticate', 
            expected_status=401, data=auth_data
        )
        
        if success and 'revoked' in response.get('detail', '').lower():
            return self.log_test("Auth After Revoke", True, "Correctly rejected revoked device")
        return self.log_test("Auth After Revoke", False, f"Response: {response}")

    def test_admin_reinstate_device(self):
        """Test reinstating revoked device"""
        if not self.device_id:
            return self.log_test("Admin Reinstate Device", False, "No device_id available")
        
        success, response = self.make_request(
            'POST', f'/api/admin/devices/{self.device_id}/reinstate', 
            expected_status=200, admin_auth=True
        )
        
        if success and response.get('status') == 'reinstated':
            return self.log_test("Admin Reinstate Device", True, f"Device {self.device_id} reinstated")
        
        return self.log_test("Admin Reinstate Device", False, f"Response: {response}")

    def test_unauthorized_admin_access(self):
        """Test admin endpoints without proper API key"""
        success, response = self.make_request(
            'GET', '/api/admin/devices', 
            expected_status=403
        )
        
        if success and 'invalid' in response.get('detail', '').lower():
            return self.log_test("Unauthorized Admin Access", True, "Correctly rejected invalid API key")
        return self.log_test("Unauthorized Admin Access", False, f"Response: {response}")

    def test_unauthorized_device_access(self):
        """Test device endpoints without proper token"""
        success, response = self.make_request(
            'GET', '/api/config', 
            expected_status=401
        )
        
        # Check for various possible error responses
        if success or (response.get('detail') and ('not authenticated' in response.get('detail', '').lower() or 
                                                  'authorization' in response.get('detail', '').lower())):
            return self.log_test("Unauthorized Device Access", True, "Correctly rejected missing token")
        return self.log_test("Unauthorized Device Access", False, f"Response: {response}")

    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 Starting RFID Cloud API Tests")
        print("=" * 50)
        
        # Basic health checks
        self.test_health_check()
        self.test_root_endpoint()
        
        # Admin functionality
        self.test_unauthorized_admin_access()
        self.test_admin_register_device()
        self.test_admin_register_duplicate()
        self.test_admin_list_devices()
        self.test_admin_get_device()
        self.test_admin_statistics()
        
        # Device authentication and functionality
        self.test_unauthorized_device_access()
        self.test_device_authenticate_invalid()
        self.test_device_authenticate()
        self.test_get_config()
        self.test_submit_readings()
        self.test_query_readings()
        self.test_heartbeat()
        
        # Device lifecycle management
        self.test_admin_revoke_device()
        self.test_device_auth_after_revoke()
        self.test_admin_reinstate_device()
        
        # Final authentication test after reinstatement
        self.test_device_authenticate()
        
        print("=" * 50)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("❌ Some tests failed!")
            failed_tests = [r for r in self.test_results if not r['success']]
            print("\nFailed tests:")
            for test in failed_tests:
                print(f"  - {test['name']}: {test['details']}")
            return 1

def main():
    tester = RFIDAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())