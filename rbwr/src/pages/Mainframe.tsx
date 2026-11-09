import { useEffect, useState } from "react";
import { SimulatorCliMode } from "@/components/SimulatorCliMode";
import { PLANT_TRANSPORT_KEY, setPlantTransport } from "@/lib/plantOperations";
import { requestUnitConsole, type ConsoleStatus } from "@/lib/workstationConsole";

const offlineStatus = "CONTROL ROOM OFFLINE\nOpen RBWR Unit 2 to connect live controls.";
const hasPermission = (permission: string) => {
  if (!sessionStorage.getItem("reactoros-debian-operator")) return true;
  return (JSON.parse(sessionStorage.getItem("reactoros-permissions") || "[]") as string[]).includes(permission);
};

export default function Mainframe() {
  const [plant, setPlant] = useState<ConsoleStatus | null>(null);
  const allowed = hasPermission("app:mainframe");

  useEffect(() => {
    if (!allowed) return;
    if (location.hostname === "127.0.0.1" && !localStorage.getItem(PLANT_TRANSPORT_KEY)) setPlantTransport("local");
    let stopped = false;
    let timer: number;
    let station: string | undefined;
    const refresh = async () => {
      const reply = await requestUnitConsole(station).catch(() => null);
      if (stopped) return;
      station = reply?.station;
      setPlant(previous => {
        if (!reply) return null;
        const assignment = reply.assignment;
        const sameStation = previous?.assignment?.roomCode === assignment?.roomCode &&
          previous?.assignment?.stationId === assignment?.stationId &&
          previous?.assignment?.unitNumber === assignment?.unitNumber;
        if (sameStation && previous?.station === reply.station && previous.status === reply.status) return previous;
        return { station: reply.station, status: reply.status, assignment: sameStation ? previous?.assignment ?? null : assignment };
      });
      timer = window.setTimeout(refresh, 750);
    };
    void refresh();
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [allowed]);

  if (!allowed) return <main className="p-4">Advanced Operator Terminal access denied.</main>;
  return (
    <SimulatorCliMode
      open
      standalone
      plantAssignment={plant?.assignment}
      liveStatus={plant?.status ?? offlineStatus}
      onCommand={async (command) => {
        if (!plant) return offlineStatus;
        const reply = await requestUnitConsole(plant.station, command).catch(() => null);
        return reply?.result ?? offlineStatus;
      }}
      onOpenDatabase={sessionStorage.getItem("reactoros-debian-operator")
        ? () => hasPermission("app:live-variables") && Boolean(window.open("/plant-tools.html?tool=database"))
        : undefined}
    />
  );
}
