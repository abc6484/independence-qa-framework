"""Start only local lab applications, never remote targets."""
import os
import subprocess
import sys
from pathlib import Path

service, source, port = sys.argv[1:]
os.chdir(source)
sys.path.insert(0, source)
if service == 'vampi':
    # Upstream seeds three globally-unique book titles using randrange(100).
    # Fix its demo-data RNG seed to avoid random duplicate-title setup failures.
    import random
    random.seed(0)
    from config import vuln_app
    vuln_app.run(host='127.0.0.1', port=int(port), debug=False, use_reloader=False)
elif service == 'dvga':
    subprocess.run([sys.executable, 'setup.py'], check=True)
    from app import app
    import core.views
    app.run(host='127.0.0.1', port=int(port), debug=False, use_reloader=False)
