"""Minimal API shell used by the setup phase.

System routes and lifecycle behavior are added in the foundational phase.
"""

from fastapi import FastAPI

app = FastAPI(title="ADR Forge Local API", version="0.1.0")
