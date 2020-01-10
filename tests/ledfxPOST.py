import requests

Body = '''
{
	"config": {
		"Audio_Channel": "Mono", 
		"blur": 0.0, "brightness": 1.0, 
		"flip": false, 
		"frequency_range": "bass", 
		"gradient_method": "cubic_ease", 
		"gradient_name": "Spectral", 
		"gradient_roll": 0, 
		"mirror": false, 
		"speed": 1.0}, 
		"name": "Fade", 
		"type": "fade"
	}
'''

# Do the HTTP post request
response = requests.post('http://127.0.0.1:8888/api/devices/105/effects', Body)
    
# Check for HTTP codes other than 200 (LedFx Deployed)
if response.status_code != 200:
    print('Status:', response.status_code, 'Problem with the request. Exiting.')
    exit()

# Report success
print('200 OK-Successfully Deployed 105 Effect')