---
name: rocketsmith
description: Design, simulate, and build model rockets with the RocketSmith MCP server.
---

Use this skill when the user needs to design a rocket, choose a motor, inspect or modify an OpenRocket file, run a flight simulation, or prepare CAD/build outputs.

At the start of each new conversation, call `rocketsmith_setup(action="check")` before using any other RocketSmith tool.

- If dependencies are ready, continue with the requested design or simulation workflow.
- If Java, OpenRocket, or PrusaSlicer is missing, explain what is unavailable and ask before calling `rocketsmith_setup(action="install")`.
- Use `workspace_create` to make a clean project workspace when the user does not already have one.
- Use `openrocket_database` to find motors, presets, and materials before choosing dimensions or components.
- Use `openrocket_component` and `openrocket_inspect` to build or revise the design iteratively rather than guessing geometry.
- Use `openrocket_flight` and `openrocket_simulate` to validate stability and flight performance before recommending the design.
- When the user asks for fabrication outputs, convert the confirmed OpenRocket dimensions into build123d or slicer-ready artifacts only after the simulation is acceptable.

Prefer concrete engineering tradeoffs. Report stability margin, motor choice, and the main design constraints that drove the result.
