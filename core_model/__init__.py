"""
The model: agents, iteration loop, metrics, signals.

Importing this package does not run anything. The entry point is
``core_model.model.run_simulation``; everything else here is a component it
uses or a measure applied to its output.

    from core_model.model import run_simulation
    from core_model.metrics import enp, tau_absolute

Submodules are imported explicitly rather than re-exported here, so that a
reader of an analysis script can see which part of the model a name came from.
"""
