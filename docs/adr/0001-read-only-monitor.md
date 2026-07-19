# propeller-vision is a read-only monitor

The propeller-engine socket protocol exposes both queries (`status`, `project`, `get_position`) and control commands (`loop-start`, `loop-stop`, `set-bpm`, `set-mode`, `create-project`, etc.). We decided propeller-vision will only ever issue the query commands and never send control/mutation commands. This keeps the tool's scope to observation only, so it can never conflict with or corrupt engine state, and avoids the risk of two tools racing to control the loop. Control (starting/stopping/tempo/mode) is left to a separate tool.
