"""
SCADA Application Startup Script
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scada_app'))

print("Starting SCADA Application...")
print("Close the application window to exit.")

try:
    from scada_app.hmi.main_window import main
    main()
except Exception as e:
    print(f"Error starting application: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)