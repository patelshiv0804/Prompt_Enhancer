import httpx

BASE_URL = "http://localhost:8000/api/v1/styles"

def test_all():
    endpoints = [
        ("GET", "/types", None),
        ("GET", "/active", None),
        ("GET", "/type/art_style", None),
        ("GET", "", None),
        ("GET", "/popular", None),
        ("GET", "/recent", None),
        ("GET", "/recommended", None),
        ("GET", "/deleted", None),
    ]

    for method, path, json_data in endpoints:
        try:
            if method == "GET":
                r = httpx.get(BASE_URL + path)
            elif method == "POST":
                r = httpx.post(BASE_URL + path, json=json_data)
            print(f"{method} {path} -> {r.status_code}")
            if r.status_code == 500:
                print("Response:", r.text)
        except Exception as e:
            print(f"{method} {path} -> Exception: {e}")

if __name__ == "__main__":
    test_all()
