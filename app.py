"""Start the app: `python app.py` (after `pip install -r requirements.txt`) or `uv run app.py`.

Opens on http://127.0.0.1:8000 and reads ./sales.csv. No account, API key or internet needed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dk_sales.web.app import main  # noqa: E402

if __name__ == "__main__":
    main()
