from pathlib import Path

ENV_TEMPLATE = """# Project Aegis Environment Variables
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
AEGIS_LAN_MODE=true
AEGIS_AUTH_ENABLED=false
AEGIS_AUTH_SECRET=
AEGIS_USERS_JSON={}
AEGIS_ENABLE_LIVE_VOICE=false
AEGIS_ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
"""

def setup_environment():
    base_dir = Path(__file__).resolve().parent.parent
    env_file = base_dir / ".env"
    
    if not env_file.exists():
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(ENV_TEMPLATE.strip() + "\n")
        print(f"[Project Aegis] Created template .env at: {env_file}")
    else:
        print(f"[Project Aegis] .env file already exists at: {env_file}")

if __name__ == "__main__":
    setup_environment()
