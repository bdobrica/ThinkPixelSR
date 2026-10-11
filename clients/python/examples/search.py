"""Run with THINKPIXEL_API_KEY and THINKPIXEL_BASE_URL supplied securely."""

import os

from thinkpixel_sr import ThinkPixelSRClient

with ThinkPixelSRClient(base_url=os.environ["THINKPIXEL_BASE_URL"]) as client:
    matches = client.search("lighthouse opening hours")
    # Print only a count; result payloads may contain private indexed content.
    print(f"Returned {len(matches.results)} chunks")
