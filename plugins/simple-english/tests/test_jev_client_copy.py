"""The vendored evals/jev_client.py must match the session-tools client byte for byte.

The test skips outside a full checkout of the development repository, such as
in Chatito. If it fails, copy
plugins/session-tools/skills/session-digest/scripts/jev_client.py over
evals/jev_client.py. Never edit the copy on its own.
"""

import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
COPY = PLUGIN_DIR / "evals" / "jev_client.py"
ORIGINAL = PLUGIN_DIR.parent / "session-tools" / "skills" / "session-digest" / "scripts" / "jev_client.py"


@unittest.skipUnless(ORIGINAL.is_file(), "session-tools is not in this checkout")
class CopyTest(unittest.TestCase):
    def test_copy_matches_session_tools(self):
        self.assertTrue(COPY.is_file(), f"{COPY} is missing")
        self.assertEqual(COPY.read_bytes(), ORIGINAL.read_bytes(),
                         "evals/jev_client.py drifted from session-tools")
