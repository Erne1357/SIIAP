"""Application factory building blocks.

Each module registers one concern on the Flask app; ``app.create_app`` calls
them in a fixed order (the order of ``before_request`` hooks matters).
"""
