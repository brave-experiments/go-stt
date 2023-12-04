import requests

r = requests.post("http://192.168.88.180:3000/process_audio",
                  data="abcd",
                  headers={'Content-Type': 'application/octet-stream'})

print(r)

