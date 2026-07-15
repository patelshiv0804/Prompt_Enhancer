import httpx
import sys

BASE_URL = "http://localhost:8000/api/v1"

def test_prompts_and_versions():
    print("=== STARTING PROMPTS & VERSIONS API TESTS ===")
    
    # Header containing user email
    headers = {"X-Current-User": "another_user@example.com"}
    
    # 1. Create a Prompt
    print("\n1. Testing POST /prompts/ (Create Prompt)...")
    payload = {
        "original_prompt": "Translate the following text to Spanish: Hello World",
        "title": "Spanish Translator"
    }
    r = httpx.post(f"{BASE_URL}/prompts/", json=payload, headers=headers)
    print("Status:", r.status_code)
    print("Response:", r.json())
    assert r.status_code == 200, "Failed to create prompt"
    
    prompt_data = r.json()["data"]
    prompt_id = prompt_data["id"]
    
    # 2. Get Prompt Detail
    print(f"\n2. Testing GET /prompts/{prompt_id} (Get Prompt)...")
    r = httpx.get(f"{BASE_URL}/prompts/{prompt_id}")
    print("Status:", r.status_code)
    print("Response:", r.json())
    assert r.status_code == 200, "Failed to retrieve prompt details"
    
    # 3. Create a new Prompt Version
    print("\n3. Testing POST /prompt-versions/ (Create Prompt Version)...")
    version_payload = {
        "version_number": 2,
        "version_type": "published",
        "content": "Translate the following text to Spanish: Hello World! How are you?",
        "change_summary": "Added greeting"
    }
    r = httpx.post(f"{BASE_URL}/prompt-versions/?prompt_id={prompt_id}", json=version_payload)
    print("Status:", r.status_code)
    print("Response:", r.json())
    assert r.status_code == 200, "Failed to create prompt version"
    version_id = r.json()["data"]["id"]
    
    # 4. List Prompt Versions
    print(f"\n4. Testing GET /prompt-versions/ (List Versions for Prompt)...")
    r = httpx.get(f"{BASE_URL}/prompt-versions/?prompt_id={prompt_id}")
    print("Status:", r.status_code)
    print("Response data count:", len(r.json()["data"]))
    assert r.status_code == 200, "Failed to list prompt versions"
    
    # 5. Get Prompt Version details
    print(f"\n5. Testing GET /prompt-versions/{version_id} (Get Version Detail)...")
    r = httpx.get(f"{BASE_URL}/prompt-versions/{version_id}")
    print("Status:", r.status_code)
    print("Response:", r.json())
    assert r.status_code == 200, "Failed to get version detail"
    
    # 6. List Prompts
    print("\n6. Testing GET /prompts/ (List Prompts)...")
    r = httpx.get(f"{BASE_URL}/prompts/")
    print("Status:", r.status_code)
    print("Response total count:", r.json()["total"])
    assert r.status_code == 200, "Failed to list prompts"
    
    # 7. Update Prompt
    print(f"\n7. Testing PUT /prompts/{prompt_id} (Update Prompt)...")
    update_payload = {
        "title": "Updated Spanish Translator"
    }
    r = httpx.put(f"{BASE_URL}/prompts/{prompt_id}", json=update_payload)
    print("Status:", r.status_code)
    print("Response title:", r.json()["data"]["title"])
    assert r.status_code == 200, "Failed to update prompt"
    
    # 8. Restore historical version
    # Let's get the version count and detail before restore
    print(f"\n8. Testing POST /prompt-versions/{prompt_id}/restore (Restore Version)...")
    # We will restore the first version (since version 2 is active now).
    # Let's fetch versions to find version 1 ID
    versions_list = httpx.get(f"{BASE_URL}/prompt-versions/?prompt_id={prompt_id}").json()["data"]
    # We want to find the draft or the first version (not the one we just created)
    version_1_id = None
    for v in versions_list:
        if v["id"] != version_id:
            version_1_id = v["id"]
            break
            
    if version_1_id:
        restore_payload = {"version_id": version_1_id}
        r = httpx.post(f"{BASE_URL}/prompt-versions/{prompt_id}/restore", json=restore_payload)
        print("Restore Status:", r.status_code)
        print("Response:", r.json())
        assert r.status_code == 200, "Failed to restore version"
    else:
        print("Skipping restore: only one version found.")
        
    print("\n=== ALL PROMPTS & VERSIONS API TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    try:
        test_prompts_and_versions()
    except Exception as e:
        print("\nTest failed with error:", e)
        sys.exit(1)
