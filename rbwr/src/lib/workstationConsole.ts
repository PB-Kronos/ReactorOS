import type { PlantAssignment } from "@/lib/plantOperations";

export const WORKSTATION_CONSOLE = "reactoros-unit2-console";

export interface ConsoleStatus {
  station: string;
  assignment: PlantAssignment | null;
  status: string;
}

export interface ConsoleRequest {
  id: string;
  station?: string;
  command?: string;
}

export interface ConsoleReply extends ConsoleStatus {
  replyTo: string;
  result?: string;
}

export function requestUnitConsole(station?: string, command?: string): Promise<ConsoleReply | null> {
  return new Promise(resolve => {
    const channel = new BroadcastChannel(WORKSTATION_CONSOLE);
    const id = crypto.randomUUID();
    const finish = (reply: ConsoleReply | null) => {
      window.clearTimeout(timeout);
      channel.close();
      resolve(reply);
    };
    const timeout = window.setTimeout(() => finish(null), 1200);
    channel.onmessage = ({ data }: MessageEvent<ConsoleReply>) => {
      if (data?.replyTo === id) finish(data);
    };
    channel.postMessage({ id, station, command } satisfies ConsoleRequest);
  });
}
