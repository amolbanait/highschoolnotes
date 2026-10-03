"""PDF through WeasyPrint, from the HTML export.

The renderer gets a URL fetcher that refuses everything: the page is self-contained, and
nothing in a guide may make the server fetch a URL or read a file.
"""

from app.export.common import ExportInfo
from app.export.html import to_html


def to_pdf(content: dict, info: ExportInfo) -> bytes:
    # Imported here: WeasyPrint loads system libraries (Pango) on import.
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher

    class NoFetch(URLFetcher):
        def fetch(self, url, headers=None):
            raise ValueError("exports do not load external resources")

    return HTML(string=to_html(content, info), url_fetcher=NoFetch(allowed_protocols=())).write_pdf()
