import requests

WLEDEffects = 'FX=0&'
WLEDHueColor = 'R=0&'

url = 'http://192.168.1.102/win&' + WLEDEffects + WLEDHueColor

x = requests.get(url)
print(x.text)
