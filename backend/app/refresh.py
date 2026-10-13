"""One-shot update for a real external scheduler: python -m app.refresh."""
import asyncio
from .service import tick
if __name__=='__main__':asyncio.run(tick())
