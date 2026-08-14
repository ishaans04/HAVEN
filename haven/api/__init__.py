"""The API tier.

Thin by design: it validates against the locked contract, sequences nothing, and
decides nothing. All logic lives in the engine and the tiers beneath it.
"""
