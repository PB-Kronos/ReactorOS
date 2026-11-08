"""Interactive-runtime smoke test; starts an isolated loopback server."""
from http.server import ThreadingHTTPServer
import threading
import time
import unittest
import json
from urllib.request import urlopen

from local_server import Handler, init_plant_bridge
from rbwr_desktop import ROOT, launch, webview, windows


class DesktopSmoke(unittest.TestCase):
    def test_control_room(self):
        results = []
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            init_plant_bridge(server)
            base = f"http://127.0.0.1:{server.server_port}"
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            launch(base + "/mainframe")
            console = windows["/mainframe"]

            def inspect():
                try:
                    if not console.events.loaded.wait(20):
                        raise AssertionError("Command console did not load")
                    for _ in range(60):
                        if console.evaluate_js("document.querySelector('h1')?.textContent.includes('ADVANCED SIMULATOR CONSOLE')"):
                            break
                        time.sleep(.25)
                    else:
                        raise AssertionError("CLI startup did not open the command console")
                    with urlopen(base + "/api/plant", timeout=2) as response:
                        assert not json.load(response)["online"], "Console started a simulator"
                    launch(base + "/reactor")
                    window = windows["/reactor"]
                    if not window.events.loaded.wait(20):
                        raise AssertionError("Control room did not load")
                    launch(base + "/manual?page=control-rods")
                    manual = windows["/manual"]
                    if not manual.events.loaded.wait(20):
                        raise AssertionError("Manual window did not load")
                    for _ in range(60):
                        if manual.evaluate_js("document.querySelector('select')?.value === 'control-rods'"):
                            break
                        time.sleep(.25)
                    else:
                        raise AssertionError("Manual did not open the requested panel")
                    for _ in range(60):
                        clicked = window.evaluate_js("""
                            (() => {
                              const button = [...document.querySelectorAll('button')]
                                .find(b => b.textContent.trim().toLowerCase() === 'control rods');
                              if (!button) return false;
                              button.click();
                              return true;
                            })()
                        """)
                        if clicked:
                            break
                        time.sleep(.25)
                    else:
                        raise AssertionError("No control rods button in embedded app")
                    for _ in range(40):
                        if window.evaluate_js("document.body.dataset.rbwrPanel === 'control-rods'"):
                            break
                        time.sleep(.25)
                    else:
                        raise AssertionError("Control rods panel did not open")
                    def read_plant():
                        with urlopen(base + "/api/plant", timeout=2) as response:
                            return json.load(response)

                    state = read_plant()
                    assert state["online"] and not state["state"]["scramPressed"], state
                    for command in ("login supervisor", "scram"):
                        console.evaluate_js(f"""
                            (() => {{
                              const input = document.querySelector('input');
                              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')
                                .set.call(input, {json.dumps(command)});
                              input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            }})()
                        """)
                        console.evaluate_js("""
                            document.querySelector('input').dispatchEvent(
                              new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
                            )
                        """)
                    for _ in range(40):
                        if read_plant()["state"]["scramPressed"]:
                            results.append(True)
                            break
                        time.sleep(.25)
                    else:
                        raise AssertionError("Standalone console SCRAM did not reach the simulator")
                except Exception as exc:
                    results.append(exc)
                finally:
                    for active_window in list(windows.values()):
                        active_window.destroy()

            try:
                webview.start(inspect, gui="edgechromium",
                              storage_path=str(ROOT / ".rbwr-test-profile"))
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(results, [True])


if __name__ == "__main__":
    unittest.main()
