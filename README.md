# ReactorOS

ReactorOS is a Windows 95-style desktop prototype with a shortcut for the
imported RBWR Unit 2 simulator.

It does **not** connect to real PLCs, hardware, networks, or external systems.

## Run

Double-click `Launch-ReactorOS.cmd`, or run:

```powershell
python .\reactor_os.py
```

Run `Setup-RBWR.cmd` once if the local desktop runtime is missing. The
Windows WebView2 runtime must already be installed. Close any older ReactorOS
window before relaunching to free port 18765.

The **RBWR Unit 2** shortcut opens a dedicated app window with the original
RBWR panels and Windows 95-style controls. ReactorOS serves the app on
loopback and stores its WebView profile in `.rbwr-profile`. Simulation saves
still use that profile's local storage; SQLite records server events.

The Start menu opens Plant Operations Terminal, Status Desk, Plant Supervisor,
Mainframe Terminal and Operator Manual as separate windows in the same desktop
host. Use `LOGIN <name>` in Plant Operations Terminal to set the local operator
identity. The reactor's **Page Manual** button opens the guide for the current
panel, and the Status Desk and Supervisor buttons open their own windows.

Use **RBWR Command Console** from Start, or run
`Launch-ReactorOS.cmd --cli`, to open the standalone Mainframe console.
It reads shared snapshots and queues commands for the RBWR control room.
Start the control room separately when you want the simulation to run.

The production server bundle includes only the workstation tools. Archive
game routes and their audio are excluded from the build.

The imported web application can be rebuilt in `rbwr` with `npm run build`
after installing its Node dependencies. Its current UI and any optional cloud
features are inherited from the source project.

The goal is a bootable offline industrial workstation: role-based login,
multi-screen operator stations, one authoritative plant service, simulated SSH
and engineering tools, automation, faults and repair, and a local historian
with service controls and an editor. The Windows build is a development host;
those shared systems and the bootable kiosk image are still pending.

Run `python test_rbwr_desktop.py` to verify that the embedded control room
loads independently, opens the Control rods panel and manual, and delivers
a simulated SCRAM from the standalone console to the running reactor.

Local programs can call `GET http://127.0.0.1:18765/api/plant` for live
temperature, pressure, APRM, turbine output, running status and SCRAM state.
The response marks the simulator offline after five seconds without an update.
To request a simulated SCRAM, send JSON `{"command":"scram"}` to
`POST /api/plant/command`. HTTP 202 means queued; check live status for
actuation. This bridge requires the control room to be open. It is a trusted
local development interface, with no role permissions or arbitrary commands.
