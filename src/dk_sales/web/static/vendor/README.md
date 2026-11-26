# Vendored libraries

| File | Library | Version | License | sha256 |
|---|---|---|---|---|
| lucide/*.svg | Lucide icons (npm `lucide-static`, `icons/`) | 1.81.0 | ISC (`lucide/LICENSE.txt`) | per file, see `tests/test_web.py::test_icons_are_vendored_lucide` |

Lucide icons are read once at startup and inlined into the page (`dk_sales.web.views.icon`), so they take the text color and need no extra request.
