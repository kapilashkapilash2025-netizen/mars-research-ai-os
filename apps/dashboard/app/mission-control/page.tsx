import type { Metadata } from "next";
import { MissionControl } from "./mission-control";

export const metadata: Metadata = {
  title: "Mission Control Simulator — Areograph Labs",
  description: "Plan, execute, and replay a deterministic simulated Mars rover mission.",
};

export default function MissionControlPage() {
  return <MissionControl />;
}
