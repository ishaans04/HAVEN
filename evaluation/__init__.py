"""Measurement of the reasoning tier.

Not part of the runtime. Nothing under `haven/` imports this package, and a test
asserts that — an evaluation harness that the system under test could reach
would be measuring itself.

The point of it is honesty about a specific risk. HAVEN's mock reads prose and
gets every scenario right; a real Granite is under no obligation to. Shipping
the measurement *before* the provider switch means a regression shows up as a
number rather than as a demo failing in front of an audience, and it means the
mock-to-Granite gap can be reported rather than hoped away.
"""
