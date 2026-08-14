"""HAVEN -- Human Adaptation & Vitality Enhancement Network.

The telemetry guard runs here, at the top of the package, because this is the
only point guaranteed to execute before any submodule -- and therefore before
any LangChain or LangGraph import can read the environment. See ``haven.offline``
for why that ordering matters.
"""

from haven.offline import disable_external_telemetry

disable_external_telemetry()
