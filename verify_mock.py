import os
import django
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    django.setup()
    from backend.services.flood_service import FloodRiskService
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)

def test_mock_service():
    print("Testing FloodRiskService with Mock Data...")
    service = FloodRiskService()
    
    # Test coordinates (Varanasi)
    lat = 25.3176
    lon = 82.9739
    
    print(f"Fetching forecast for {lat}, {lon}")
    result = service.get_flood_forecast(lat, lon)
    
    if result:
        print("\n✅ Verification SUCCESS!")
        print("Source:", result.get('source'))
        print("Mock Mode:", result.get('mock'))
        print("Risk Assessment:", result.get('risk_assessment', {}).get('overall_risk'))
        print("Current Discharge:", result.get('daily', {}).get('river_discharge', [])[0])
    else:
        print("\n❌ Verification FAILED: No data returned")

if __name__ == "__main__":
    test_mock_service()
