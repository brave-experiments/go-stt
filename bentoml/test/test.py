import requests

r = requests.post("http://localhost:3000/process_audio",
                  data="abc",
                  headers={'Content-Type': 'application/octet-stream'})

print(r)

