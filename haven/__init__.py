"""HAVEN -- Human Adaptation & Vitality Enhancement Network.

Two things happen here, in this order, and the order is the point.

**`.env` is loaded first.** Every setting in :mod:`haven.config` is resolved at
import time -- ``LLM = LLMSettings()`` runs on the first import of that module,
and each field reads ``os.getenv`` through a ``default_factory``. So anything
that is going to populate the environment has to do it before then, and this
module is the only place guaranteed to run before any submodule.

``override=False``: a variable already exported wins over the file. That keeps
CI, the Dockerfile and ``tests/conftest.py`` -- all of which set variables
directly -- behaving exactly as they did before the file was read at all.

**Then the telemetry guard runs**, which is also why it has to be second. If the
guard ran first, a ``LANGSMITH_TRACING=true`` sitting in somebody's ``.env``
would be loaded straight over the top of it and the offline guarantee would be
gone -- silently, since tracing failing open looks like nothing. Loading first
and clearing second means the file can supply credentials but cannot switch
telemetry back on. ``tests/test_config_env.py`` pins that ordering, and fails if
these two lines are swapped.

See ``haven.offline`` for what the guard covers and why it must precede any
LangChain import.
"""

from dotenv import load_dotenv

from haven.offline import disable_external_telemetry

load_dotenv(override=False)
disable_external_telemetry()
