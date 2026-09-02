"""Persistent seismic models will live here when local event storage is introduced.

USGS events are currently read-through, cached external data, so no database
model or migration is necessary. Keeping this module app-local reserves a
clear home for future multi-source event, alert, and analysis models.
"""
