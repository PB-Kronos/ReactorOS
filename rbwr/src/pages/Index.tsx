import { useEffect, useRef, useState } from "react";
import { ensureLeaderboardPlayer, getLeaderboard } from "@/lib/leaderboard";
import { Button } from "@/components/ui/button";
import {
  GREETING_HELP,
  GREETING_TERMINAL_RESPONSES,
} from "@/lib/terminalCommands";

const workstationApps = [
  ["reactor", "app:reactor", "/reactor"],
  ["console", "app:mainframe", "/mainframe"],
  ["supervisor", "app:supervisor", "/supervisor"],
  ["status-desk", "app:status-desk", "/status-desk"],
  ["manual", "app:manual", "/manual"],
  ["live-variables", "app:live-variables", "/plant-tools.html?tool=database"],
  ["events", "app:events", "/plant-tools.html?tool=server"],
  ["files", "app:files", ""],
  ["editor", "app:editor", ""],
  ["images", "app:images", ""],
  ["browser", "app:browser", ""],
  ["users", "users:manage", ""],
] as const;

async function workstationRequest(path: string, body?: object, token?: string) {
  const response = await fetch(path, body ? {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-ReactorOS-Session": token } : {}),
    },
    body: JSON.stringify(body),
  } : { cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

const workstationHelp = [
  "help                     Show commands",
  "apps                     List apps you can open",
  "open <app>               Open or focus an app",
  "whoami / roles           Show your Debian account or ReactorOS roles",
  "status                   Check the local server and plant connection",
  "time / date              Show local date and time",
  "uptime                   Show time since this terminal opened",
  "echo <text> / clear      Print text or clear the screen",
].join("\n");

function WorkstationTerminal() {
  const [input, setInput] = useState("");
  const [output, setOutput] = useState(["ReactorOS Plant Operations Terminal", "Type help to list commands."]);
  const [busy, setBusy] = useState(false);
  const outputRef = useRef<HTMLPreElement>(null);
  const openedAt = useRef(performance.now());
  useEffect(() => {
    outputRef.current?.scrollTo(0, outputRef.current.scrollHeight);
  }, [output]);

  async function execute(command: string) {
    const [verb] = command.split(/\s+/, 1);
    const argument = command.slice(verb.length).trimStart();
    const action = verb.toLowerCase();
    if (action === "echo") return argument;
    if (action === "time" || action === "date") return new Date().toLocaleString();
    if (action === "uptime") return `Terminal open for ${Math.floor((performance.now() - openedAt.current) / 1000)} seconds.`;
    const operator: { name: string; roles: string[]; permissions: string[] } = await workstationRequest("/api/operator");
    const can = (permission: string) => operator.permissions.includes(permission);
    if (action === "help") return workstationHelp + (can("terminal:execute")
      ? "\nterminal <command>       Run a Debian command in its own terminal window" : "");
    if (action === "whoami") return operator.name;
    if (action === "roles") return operator.roles.join(", ") || "No roles assigned.";
    if (action === "status") {
      const service = await workstationRequest("/api/status");
      const plant = await workstationRequest("/api/plant").catch(() => null);
      return `Local server: ${service.status}\nRBWR link: ${plant ? (plant.online ? "online" : "offline") : "unavailable"}`;
    }
    if (action === "apps") {
      return workstationApps.filter(([, permission]) => can(permission)).map(([app]) => app).join("\n")
        || "No applications available.";
    }
    if (action === "terminal") {
      if (!can("terminal:execute")) return "Permission denied for Debian terminal.";
      if (!argument) return "Usage: terminal <command>";
      await workstationRequest("/api/desktop/terminal", { command: argument }, sessionStorage.getItem("reactoros-terminal-token") || undefined);
      return "Opened Debian Terminal.";
    }
    const app = workstationApps.find(([name]) => name === (action === "open" ? argument.toLowerCase() : action));
    if (!app) return action === "open" ? "Unknown app. Type apps for available names." : "Unknown command. Type help.";
    const [name, permission, route] = app;
    if (!can(permission)) return `Permission denied for ${name}.`;
    if (route) {
      if (!window.open(route)) return "App could not open. Try the Start menu.";
    } else {
      await workstationRequest("/api/desktop/launch", { app: name });
    }
    return `Opened ${name}.`;
  }

  return (
    <main className="flex h-screen flex-col gap-2 bg-[#c0c0c0] p-2 font-mono text-black">
      <pre ref={outputRef} role="log" className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap border-2 border-inset border-[#808080] bg-black p-3 text-[#eee]">
        {output.join("\n")}
      </pre>
      <form className="flex items-center gap-2" onSubmit={async (event) => {
        event.preventDefault();
        const command = input.trim();
        if (!command || busy) return;
        setInput("");
        if (command.toLowerCase() === "clear") {
          setOutput([]);
          return;
        }
        setBusy(true);
        const response = await execute(command).catch(error => String(error.message || error));
        setOutput(previous => [...previous.slice(-198), command.match(/^terminal\s/i) ? "> terminal [command sent]" : `> ${command}`, response]);
        setBusy(false);
      }}>
        <span aria-hidden="true">&gt;</span>
        <input aria-label="Command" autoFocus autoComplete="off" spellCheck={false} value={input}
          onChange={event => setInput(event.target.value)} className="min-w-0 flex-1 border-2 border-[#808080] bg-white px-2 py-1" />
        <button disabled={busy} className="border-2 border-t-white border-l-white border-b-[#404040] border-r-[#404040] px-3 py-1">Run</button>
      </form>
    </main>
  );
}

const Index = () => sessionStorage.getItem("reactoros-debian-operator")
  ? <WorkstationTerminal />
  : <SimulatorGreeting />;

const SimulatorGreeting = () => {
  const [input, setInput] = useState("");
  const [booting, setBooting] = useState(true);
  const [lines, setLines] = useState<string[]>([]);
  const [history, setHistory] = useState<string[]>([
    "UNIT 2: THE BWR SIM // OPERATOR ACCESS TERMINAL",
    "Guest entry is available. LOGIN <yourname> is recommended to record points. Type HELP for commands.",
  ]);
  const [operatorName, setOperatorName] = useState(
    () => localStorage.getItem("unit2-operator-name") || "",
  );
  const introStarted = useRef(false);
  const terminalOutputRef = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const output = terminalOutputRef.current;
    if (output) output.scrollTop = output.scrollHeight;
  }, [booting, lines, history]);
  useEffect(() => {
    const boot = [
      "[ OK ] Loading Unit 2 kernel",
      "[ OK ] Verifying operator terminal memory",
      "[ OK ] Initializing reactor physics model",
      "[ OK ] Loading 6 × 6 control-rod programme",
      "[ OK ] Starting MCC process controller",
      "[ OK ] Calibrating reactor, Hotwell and DA level instruments",
      "[ OK ] Establishing condensate and feedwater flow paths",
      "[ OK ] Arming RPS channels A / B",
      "[ OK ] Checking ECCS train availability",
      "[ OK ] Polling condenser circulation and vacuum controls",
      "[ OK ] Linking turbine and grid controls",
      "[ OK ] Loading annunciator matrix",
      "[ OK ] Restoring public simulator workspace",
      "",
      "",
      "",
      "[ OK ] Running final interface diagnostics",
      "Unit 2 operator terminal ready.",
    ];
    let index = 0;
    const timer = window.setInterval(() => {
      setLines((current) => [...current, boot[index]]);
      index += 1;
      if (index === boot.length) {
        window.clearInterval(timer);
        window.setTimeout(() => setBooting(false), 700);
      }
    }, 500);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    const start = new Audio("/sounds/booting-start.mp3");
    const loop = new Audio("/sounds/booting-loop.mp3");
    start.volume = 0.34;
    loop.volume = 0.28;
    loop.loop = true;
    const begin = () => {
      if (introStarted.current) return;
      introStarted.current = true;
      void start.play().catch(() => {
        introStarted.current = false;
      });
    };
    const beginLoop = () => {
      void loop.play().catch(() => {});
    };
    const unlock = () => begin();
    start.addEventListener("ended", beginLoop);
    void start
      .play()
      .then(() => {
        introStarted.current = true;
      })
      .catch(() => {
        window.addEventListener("pointerdown", unlock, { once: true });
        window.addEventListener("keydown", unlock, { once: true });
      });
    return () => {
      start.removeEventListener("ended", beginLoop);
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
      start.pause();
      start.currentTime = 0;
      loop.pause();
      loop.currentTime = 0;
    };
  }, []);
  const greetingHelp = (topic: string) => {
    const details: Record<string, string> = {
      login: "LOGIN <yourname>\nRegisters your public operator name in this browser and lets the leaderboard track your score.\nExample: LOGIN UnitOperator",
      logout: "LOGOUT\nEnds the score-recording session and switches to guest mode. The reactor remains available, but guest operation earns no points.",
      start: "START — BASIC OPERATOR PATH\n1. LOGIN <yourname> to record points (guest operation is allowed).\n2. Enter REACTOR and check Overview plus RPS for clear trip conditions.\n3. Energize Bus A, establish condenser vacuum, and start MCC circulation.\n4. Start with the tutorial, Auto APRM, or the normal SRM → IRM rod sequence.\n5. When steam conditions are ready, run up, synchronize, and load the turbine.",
      operations: "OPERATIONS — NORMAL CONTROL ORDER\nElectrical power → protection clear → condenser vacuum → MCC flow and level control → controlled APRM increase → turbine run-up → synchronization → load following.\n\nAfter every major change, check reactor level, pressure, period, condenser pressure, Bus A/S availability, and annunciators.",
      multiunit: "MULTIUNIT\nDisplays the V2.3.2 shared-plant and local-operation guide: Supervisor Rooms, Unit 1/2 station links, demand allocation, interlock prerequisites, scoring, offline local transport, and LOOP recovery.",
      status: "STATUS\nDisplays the basic public system state and the current greeting-terminal operator name.",
      leaderboard: "LEADERBOARD\nShows the top five locally stored operators plus your score and ranking after you login.",
      time: "TIME\nDisplays the local date and time from your device.",
      date: "DATE\nAlias for TIME; displays your device's local date and time.",
      whoami: "WHOAMI\nDisplays the currently registered greeting-terminal operator name.",
      uptime: "UPTIME\nDisplays the elapsed time since this browser page was opened.",
      echo: "ECHO <text>\nPrints text back into the terminal. Example: ECHO systems nominal",
      fortune: "FORTUNE\nDisplays a random Unit 2 operator message.",
      clear: "CLEAR\nClears the visible terminal history and restores the greeting banner.",
    };
    return details[topic] || `No detailed entry for ${topic.toUpperCase()}.\n\n${GREETING_HELP}`;
  };
  const run = async () => {
    const command = input.trim();
    if (!command) return;
    const [verb, ...args] = command.split(/\s+/);
    const lower = verb.toLowerCase();
    const argument = args.join(" ").trim();
    let response = "Unknown command. Type HELP.";
    if (GREETING_TERMINAL_RESPONSES[lower])
      response = GREETING_TERMINAL_RESPONSES[lower];
    else if (lower === "help")
      response = argument ? greetingHelp(argument.toLowerCase()) : GREETING_HELP;
    else if ((lower === "login" || lower === "logout") && sessionStorage.getItem("reactoros-debian-operator")) {
      response = `Operator identity comes from your Debian session: ${operatorName}.`;
    } else if (lower === "login") {
      const name = argument.replace(/[^a-z0-9 _-]/gi, "").trim().slice(0, 24);
      if (!name) response = "Usage: LOGIN <yourname>\nExample: LOGIN UnitOperator";
      else {
        try {
          await ensureLeaderboardPlayer(name);
        } catch (error) {
          const detail = error instanceof Error
            ? error.message
            : typeof error === "object" && error && "message" in error
              ? String((error as { message: unknown }).message)
              : String(error || "unable to create the persistent score profile");
          response = `LOGIN REJECTED — ${detail}`;
          setHistory(previous => [...previous, `> ${command}`, response]);
          setInput("");
          return;
        }
        localStorage.setItem("unit2-operator-name", name);
        try {
          const scores = JSON.parse(localStorage.getItem("unit2-operator-scores") || "{}");
          if (!scores[name]) scores[name] = { points: 0, lastSeen: Date.now() };
          localStorage.setItem("unit2-operator-scores", JSON.stringify(scores));
        } catch { /* A malformed old score store is safely replaced on scoring. */ }
        setOperatorName(name);
        response = `LOGIN ACCEPTED — ${name}\nOperator score profile registered. You may now use REACTOR.`;
      }
    } else if (lower === "logout") {
      localStorage.removeItem("unit2-operator-name");
      setOperatorName("");
      response = "LOGOUT COMPLETE — GUEST MODE ACTIVE. You may still enter the reactor, but points will not be recorded.";
    }
    else if (lower === "status")
      response = `System bus: ONLINE\nRPS: ARMED\nECCS: AVAILABLE\nOperator: ${operatorName || "GUEST (NO POINTS)"}`;
    else if (lower === "leaderboard") {
      try {
        const remote = await getLeaderboard();
        const scores = remote.length ? Object.fromEntries(remote.map(entry => [entry.display_name, { points: entry.points }])) : JSON.parse(localStorage.getItem("unit2-operator-scores") || "{}");
        const ranked = Object.entries(scores)
          .map(([name, entry]: [string, unknown]) => [name, Number((entry as { points?: unknown } | undefined)?.points || 0)] as const)
          .sort(([, left], [, right]) => right - left);
        const topFive = ranked.slice(0, 5);
        const rows = topFive.length
          ? topFive.map(([name, points], index) => `${index + 1}. ${name} — ${points.toFixed(1)} pts`).join("\n")
          : "No scored operators yet.";
        const rank = operatorName ? ranked.findIndex(([name]) => name === operatorName) + 1 : 0;
        const ownPoints = operatorName ? Number(scores[operatorName]?.points || 0) : 0;
        response = `UNIT 2 ${remote.length ? "GLOBAL" : "LOCAL"} LEADERBOARD\n${rows}\n\n${operatorName ? `YOUR POSITION: #${rank || "—"} / ${ranked.length || "—"}\nYOUR SCORE: ${ownPoints.toFixed(1)} pts` : "LOGIN <yourname> to view your personal score and rank."}`;
      } catch {
        response = "Leaderboard data is unavailable. Log in again to create a new operator profile.";
      }
    }
    else if (['reactor', 'console', 'supervisor'].includes(lower)) {
      response = 'Open workstation programs from the ReactorOS Start menu.';
    } else if (lower === "time" || lower === "date")
      response = new Intl.DateTimeFormat(undefined, {
        dateStyle: "full",
        timeStyle: "medium",
      }).format(new Date());
    else if (lower === "whoami")
      response = operatorName || "GUEST — use LOGIN <yourname> to register.";
    else if (lower === "uptime")
      response = `Terminal session: ${Math.floor(performance.now() / 1000)} seconds`;
    else if (lower === "echo") response = argument || "";
    else if (lower === "fortune") {
      const fortunes = [
        "A stable core starts with a stable operator.",
        "The best transient is the one you anticipated.",
        "Check the annunciators before they check you.",
        "A quiet control room is usually a good sign.",
      ];
      response = fortunes[Math.floor(Math.random() * fortunes.length)];
    } else if (lower === "clear") {
      setHistory([
        "UNIT 2: THE BWR SIM // OPERATOR ACCESS TERMINAL",
        "Guest entry is available. LOGIN <yourname> is recommended to record points. Type HELP for commands.",
      ]);
      setInput("");
      return;
    }
    setHistory((current) => [...current.slice(-18), `> ${command}`, response]);
    setInput("");
  };
  return (
    <main className="min-h-screen overflow-hidden bg-[#050b0d] p-4 font-mono text-emerald-300 selection:bg-emerald-400 selection:text-black sm:p-8">
      <div className="pointer-events-none fixed inset-0 opacity-20 [background-image:linear-gradient(rgba(52,211,153,.12)_1px,transparent_1px),linear-gradient(90deg,rgba(52,211,153,.12)_1px,transparent_1px)] [background-size:32px_32px]" />
      <section className="relative mx-auto flex min-h-[calc(100vh-2rem)] max-w-6xl flex-col border border-emerald-500/50 bg-black/75 p-5 shadow-[0_0_60px_rgba(16,185,129,.18)] sm:p-8">
        <header className="mb-8 flex flex-wrap items-center justify-between gap-3 border-b border-emerald-500/40 pb-4">
          <div>
            <p className="text-xs tracking-[.28em] text-emerald-500">
              UNIT 2 // THE BWR SIM
            </p>
            <h1 className="text-xl font-black text-emerald-200 sm:text-3xl">
              PLANT OPERATIONS TERMINAL
            </h1>
          </div>
          <span className="border border-emerald-500/60 px-3 py-1 text-xs">
            {booting ? "BOOTING" : "SYSTEM ONLINE"}
          </span>
        </header>
        <div className="grid flex-1 gap-8 lg:grid-cols-[1.5fr_1fr]">
          <section className="flex flex-col justify-center">
            <pre ref={terminalOutputRef} className="min-h-72 max-h-[52vh] overflow-y-auto whitespace-pre-wrap border-l-2 border-emerald-400 bg-emerald-950/20 p-5 text-sm leading-7 text-emerald-200 sm:text-base">
              {booting ? lines.join("\n") : history.join("\n")}
              {booting && "\n_"}
            </pre>
            {!booting && (
              <div className="mt-5 space-y-3">
                <div className="flex gap-2">
                  <span className="py-3 text-emerald-400">unit2@operator:~$</span>
                  <input
                    autoFocus
                    className="min-w-0 flex-1 border-b border-emerald-400 bg-transparent px-2 py-3 text-emerald-100 outline-none"
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={(event) => event.key === "Enter" && void run()}
                    placeholder="help"
                  />
                  <Button
                    onClick={() => void run()}
                    className="bg-emerald-500 text-black hover:bg-emerald-300"
                  >
                    RUN
                  </Button>
                </div>
              </div>
            )}
          </section>
          <aside className="space-y-4">
            <section className="border border-emerald-700/60 bg-emerald-950/15 p-5 text-sm">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-bold text-emerald-100">
                  LIVE SYSTEM SUMMARY
                </h2>
                <span className="border border-emerald-500 px-2 py-1 text-xs text-emerald-200">
                  V2.3.2
                </span>
              </div>
              <dl className="space-y-3">
                <div className="flex justify-between">
                  <dt>Reactor core</dt>
                  <dd>STANDBY</dd>
                </div>
                <div className="flex justify-between">
                  <dt>RPS monitoring</dt>
                  <dd>ARMED</dd>
                </div>
                <div className="flex justify-between">
                  <dt>ECCS</dt>
                  <dd>AVAILABLE</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Console access</dt>
                  <dd>PUBLIC SANDBOX</dd>
                </div>
              </dl>
            </section>
            <section className="border border-cyan-700/50 bg-cyan-950/15 p-5 text-xs text-cyan-100">
              <h2 className="mb-3 font-bold text-cyan-200">UPDATE TO V2.3.2</h2>
              <ul className="space-y-2">
                <li>
                  • Local plant operations: run the full Supervisor, Unit 1/2,
                  station, multiwindow, PMS, and phone system on one computer
                  without Supabase or an internet connection.
                </li>
                <li>
                  • Synchronization: MCR is the single reactor-physics
                  authority; specialist stations send controls without fighting
                  pressure, RPM, levels, or kinetics.
                </li>
                <li>
                  • MCC / recirculation: Hotwell Auto now has a ±0.25 m pump
                  deadband; live recirculation kg/s displays and cavitation
                  clearance at 19% rod APRM are corrected.
                </li>
                <li>• Resilience: persisted browser checkpoints and a cached production app shell support outage recovery.</li>
                <li>
                  • Multi-unit: Supervisor demand allocation, station links,
                  Unit Interlock, and the Status Desk remain available in both
                  online and local transport modes.
                </li>
              </ul>
            </section>
            <p className="border-t border-emerald-900 pt-3 text-xs text-emerald-600">
              Use HELP or VERSION in the terminal. Fullscreen is requested when
              entering a workspace.
            </p>
          </aside>
        </div>
      </section>
    </main>
  );
};
export default Index;
