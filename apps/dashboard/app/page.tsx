import type { Metadata } from "next";
import { ResearchDashboard } from "./research-dashboard";

export const metadata: Metadata = {
  title: "Mars Knowledge Console",
  description: "Traceable Mars research with source-grounded answers.",
};

export default function Home() {
  return <ResearchDashboard />;
}
