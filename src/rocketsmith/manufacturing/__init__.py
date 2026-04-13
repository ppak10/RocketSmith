"""Manufacturing translation for RocketSmith.

Takes OpenRocket logical designs (component trees) and produces physical
parts manifests tailored for a specific manufacturing method. Today the
supported method is additive manufacturing (FDM/SLA); traditional and
hybrid builds are planned future work.

The translation logic mirrors the rules documented in the
``design-for-additive-manufacturing`` skill — the skill is the narrative
reference for humans and agents, this module is the deterministic
implementation that gets called by the MCP tool.
"""
