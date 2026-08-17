import requests

url = "http://localhost:11434/api/generate"

data = {
    "model": "mistral",
    "prompt": "Explain probability in simple words",
    "stream": False
}

r = requests.post(url, json=data)
print(r.json()["response"])
