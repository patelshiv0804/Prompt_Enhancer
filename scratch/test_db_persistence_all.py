import httpx
import sys

BASE_URL = "http://localhost:8000/api/v1"

def run_db_persistence_tests():
    print("=== STARTING COMPREHENSIVE DB PERSISTENCE VERIFICATION ===")

    # -------------------------------------------------------------
    # 1. PROFILE TEST
    # -------------------------------------------------------------
    print("\n--- 1. Testing Profile Persistence ---")
    email = "persistent_user@example.com"
    
    # POST - Create
    r = httpx.post(f"{BASE_URL}/profiles/", json={"email": email, "full_name": "Persistent User"})
    assert r.status_code == 200, f"Profile create failed: {r.text}"
    profile_id = r.json()["data"]["id"]
    print(f"Profile created via API: id={profile_id}")
    
    # GET - Fetch and verify persistence
    r = httpx.get(f"{BASE_URL}/profiles/")
    assert r.status_code == 200
    profiles = r.json()["data"]
    matched_profile = next((p for p in profiles if p["id"] == profile_id), None)
    assert matched_profile is not None, "Profile was not found in database via GET list"
    assert matched_profile["email"] == email, "Saved profile email mismatch"
    print("Profile persistence verified successfully via GET list!")

    # -------------------------------------------------------------
    # 2. AI MODEL TEST
    # -------------------------------------------------------------
    print("\n--- 2. Testing AI Model Persistence ---")
    model_name = "claude-3-5-sonnet"
    
    # POST - Create
    r = httpx.post(f"{BASE_URL}/ai-models/", json={
        "provider": "anthropic",
        "model_name": model_name,
        "description": "Anthropic flagship model",
        "is_active": True,
        "supports_analysis": True,
        "supports_optimization": True
    })
    assert r.status_code == 200, f"AI Model create failed: {r.text}"
    model_id = r.json()["data"]["id"]
    print(f"AI Model created via API: id={model_id}")
    
    # PUT - Update
    r = httpx.put(f"{BASE_URL}/ai-models/{model_id}", json={
        "description": "Anthropic updated sonnet description"
    })
    assert r.status_code == 200
    
    # GET - Fetch and verify persistence + update
    r = httpx.get(f"{BASE_URL}/ai-models/{model_id}")
    assert r.status_code == 200
    model_data = r.json()["data"]
    assert model_data["model_name"] == model_name, "Saved AI model name mismatch"
    assert model_data["description"] == "Anthropic updated sonnet description", "Saved AI model update not reflected"
    print("AI Model persistence and updates verified successfully via GET!")

    # -------------------------------------------------------------
    # 3. TEMPLATE TEST
    # -------------------------------------------------------------
    print("\n--- 3. Testing Template Persistence ---")
    template_title = "Translation Template"
    
    # POST - Create
    r = httpx.post(f"{BASE_URL}/templates/", json={
        "title": template_title,
        "description": "Template to optimize translations",
        "body": "Translate {text} to Spanish",
        "mode": "translation",
        "category": "language",
        "ai_model_id": model_id
    })
    assert r.status_code == 200, f"Template create failed: {r.text}"
    template_id = r.json()["data"]["id"]
    print(f"Template created via API: id={template_id}")
    
    # PUT - Update
    r = httpx.put(f"{BASE_URL}/templates/{template_id}", json={
        "category": "updated-language"
    })
    assert r.status_code == 200
    
    # GET - Fetch and verify persistence + update
    r = httpx.get(f"{BASE_URL}/templates/{template_id}")
    assert r.status_code == 200
    template_data = r.json()["data"]
    assert template_data["title"] == template_title, "Saved template title mismatch"
    assert template_data["category"] == "updated-language", "Saved template update not reflected"
    print("Template persistence and updates verified successfully via GET!")

    # -------------------------------------------------------------
    # 4. PROMPT TEST
    # -------------------------------------------------------------
    print("\n--- 4. Testing Prompt Persistence ---")
    prompt_original = "Optimize this for translation"
    
    # POST - Create
    headers = {"X-Current-User": email}
    r = httpx.post(f"{BASE_URL}/prompts/", headers=headers, json={
        "original_prompt": prompt_original,
        "title": "Translate Task",
        "ai_model_id": model_id,
        "template_id": template_id
    })
    assert r.status_code == 200, f"Prompt create failed: {r.text}"
    prompt_id = r.json()["data"]["id"]
    print(f"Prompt created via API: id={prompt_id}")
    
    # PUT - Update
    r = httpx.put(f"{BASE_URL}/prompts/{prompt_id}", json={
        "title": "Updated Translate Task"
    })
    assert r.status_code == 200
    
    # GET - Fetch and verify persistence + update
    r = httpx.get(f"{BASE_URL}/prompts/{prompt_id}")
    assert r.status_code == 200
    prompt_data = r.json()["data"]
    assert prompt_data["original_prompt"] == prompt_original, "Saved prompt mismatch"
    assert prompt_data["title"] == "Updated Translate Task", "Saved prompt update not reflected"
    print("Prompt persistence and updates verified successfully via GET!")

    # -------------------------------------------------------------
    # 5. PROMPT VERSION TEST
    # -------------------------------------------------------------
    print("\n--- 5. Testing Prompt Version Persistence ---")
    version_content = "Optimized translation body"
    
    # POST - Create Version
    r = httpx.post(f"{BASE_URL}/prompt-versions/?prompt_id={prompt_id}", json={
        "version_number": 1,
        "version_type": "published",
        "content": version_content,
        "change_summary": "Initial version"
    })
    assert r.status_code == 200, f"Prompt version create failed: {r.text}"
    version_id = r.json()["data"]["id"]
    print(f"Prompt version created via API: id={version_id}")
    
    # GET - Fetch and verify persistence
    r = httpx.get(f"{BASE_URL}/prompt-versions/{version_id}")
    assert r.status_code == 200
    version_data = r.json()["data"]
    assert version_data["content"] == version_content, "Saved version content mismatch"
    print("Prompt version persistence verified successfully via GET!")

    print("\n=== COMPREHENSIVE DB PERSISTENCE VERIFICATION PASSED! ===")

if __name__ == "__main__":
    try:
        run_db_persistence_tests()
    except Exception as e:
        print("\nVerification failed:", e)
        sys.exit(1)
