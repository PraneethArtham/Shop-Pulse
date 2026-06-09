import os
import sys
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

# ── Validation ─────────────────────────────────────────────────
if not SUPABASE_URL:
    sys.exit(
        "\n❌  SUPABASE_URL is missing.\n"
        "    Create a .env file in the ShopPulse/ root with:\n\n"
        "        SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co\n"
        "        SUPABASE_KEY=your_service_role_key\n\n"
        "    Get these from: https://supabase.com → your project → Settings → API\n"
    )

if not SUPABASE_KEY:
    sys.exit(
        "\n❌  SUPABASE_KEY is missing.\n"
        "    Add it to your .env file:\n\n"
        "        SUPABASE_KEY=your_service_role_key\n\n"
        "    Get it from: https://supabase.com → your project → Settings → API\n"
        "    Use the 'service_role' key (NOT the anon/public key).\n"
    )

if not SUPABASE_URL.startswith("https://"):
    sys.exit(
        f"\n❌  SUPABASE_URL looks wrong: '{SUPABASE_URL}'\n"
        "    It must start with https://  e.g.:\n"
        "        SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co\n"
    )

# ── Create client ──────────────────────────────────────────────
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    sys.exit(
        f"\n❌  Could not connect to Supabase: {e}\n\n"
        "    Check that:\n"
        "      1. SUPABASE_URL is correct  (Settings → API → Project URL)\n"
        "      2. SUPABASE_KEY is the service_role secret key  (NOT the anon key)\n"
        "      3. Your project is active at https://supabase.com\n"
    )
