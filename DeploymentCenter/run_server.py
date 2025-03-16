from waitress import serve 
import logging 
import app 
logging.basicConfig(filename=r'C:\Users\User\repos\Inventarsystem\logs\dc_2025-03-16_08-57-41.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s') 
print("Starting DeploymentCenter server on http://localhost:5001") 
serve(app.app, host='0.0.0.0', port=5001) 
