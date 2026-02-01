// src/app/page.tsx
"use client";

import { useMemo, useState } from "react";
import { Topbar } from "@/components/Topbar";
import { mockIncidents } from "@/lib/mock";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import type { Incident, Status } from "@/lib/types";

export default function Dashboard() {
  const { data: incidents, refetch: refreshIncidents } = usePolling(
    async () => {
      try {
        const data = await api.getIncidents();
        return data.length > 0 ? data : mockIncidents;
      } catch (error) {
        console.error("Failed to fetch incidents:", error);
        return mockIncidents;
      }
    },
    { interval: 5000 }
  );

  const [selectedIncidentId, setSelectedIncidentId] = useState<string>(
    mockIncidents[0]?.id
  );

  const selectedIncident = useMemo<Incident | undefined>(() => {
    const list = incidents && incidents.length > 0 ? incidents : mockIncidents;
    return list.find((item) => item.id === selectedIncidentId) || list[0];
  }, [incidents, selectedIncidentId]);

  const handleRefresh = () => {
    refreshIncidents();
  };

  const stageOrder = [
    { key: "OBSERVE", title: "Observe", description: "Ingest signals and cluster events" },
    { key: "REASON", title: "Reason", description: "Derive root cause and confidence" },
    { key: "DECIDE", title: "Decide", description: "Select response and validate policy" },
    { key: "ACT", title: "Act", description: "Execute remediation and confirm" },
  ];

  const statusToStageIndex: Record<Status, number> = {
    investigating: 0,
    monitoring: 1,
    acting: 3,
    resolved: 4,
  };

  const currentStageIndex = selectedIncident
    ? statusToStageIndex[selectedIncident.status]
    : 0;

  const getStageState = (index: number) => {
    if (currentStageIndex >= 4) return "complete";
    if (index < currentStageIndex) return "complete";
    if (index === currentStageIndex) return "active";
    return "pending";
  };

  return (
    <div className="min-h-screen pt-16 pb-12">
      <Topbar title="Incident Pipeline" onRefresh={handleRefresh} />

      <main className="max-w-7xl mx-auto px-8 space-y-8">
        <section className="bg-neutral-900 rounded-lg p-7">
          <div className="flex items-start justify-between gap-6">
            <div>
              <p className="text-xs uppercase tracking-wide text-neutral-500 mb-2">Active Ticket</p>
              <h1 className="text-2xl font-semibold text-neutral-100">
                {selectedIncident?.title || "No active incident"}
              </h1>
              <p className="text-sm text-neutral-400 mt-2">
                {selectedIncident?.description || "No incident data available."}
              </p>
            </div>
            {selectedIncident && (
              <div className="text-right">
                <p className="text-xs uppercase tracking-wide text-neutral-500">Severity</p>
                <p className="text-sm font-semibold text-neutral-200 mt-1">
                  {selectedIncident.severity.toUpperCase()}
                </p>
                <p className="text-xs uppercase tracking-wide text-neutral-500 mt-3">Status</p>
                <p className="text-sm font-semibold text-neutral-200 mt-1">
                  {selectedIncident.status}
                </p>
                <p className="text-xs uppercase tracking-wide text-neutral-500 mt-3">Confidence</p>
                <p className="text-lg font-semibold text-neutral-100 mt-1">
                  {selectedIncident.confidence}%
                </p>
              </div>
            )}
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm uppercase tracking-wide text-neutral-500">Pipeline Stages</h2>
            <p className="text-xs text-neutral-600">
              {selectedIncident ? `Incident ${selectedIncident.id}` : "No incident selected"}
            </p>
          </div>
          <div className="grid grid-cols-4 gap-4">
            {stageOrder.map((stage, index) => {
              const state = getStageState(index);
              const stateStyles =
                state === "active"
                  ? "border-blue-500/40 bg-neutral-900"
                  : state === "complete"
                  ? "border-green-500/30 bg-neutral-900/60"
                  : "border-neutral-800 bg-neutral-900/40";
              const stateLabel =
                state === "active" ? "Active" : state === "complete" ? "Complete" : "Pending";

              return (
                <div
                  key={stage.key}
                  className={`rounded-lg border p-5 transition-colors ${stateStyles}`}
                >
                  <p className="text-xs uppercase tracking-wide text-neutral-500">{stage.key}</p>
                  <h3 className="text-lg font-semibold text-neutral-100 mt-2">{stage.title}</h3>
                  <p className="text-sm text-neutral-400 mt-2 leading-relaxed">
                    {stage.description}
                  </p>
                  <p className="text-xs text-neutral-500 mt-4">{stateLabel}</p>
                </div>
              );
            })}
          </div>
        </section>

        <section className="grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-6">
            <div className="bg-neutral-900 rounded-lg p-7">
              <h2 className="text-sm uppercase tracking-wide text-neutral-500 mb-4">
                Evidence
              </h2>
              {selectedIncident?.evidence?.length ? (
                <ul className="space-y-2 text-sm text-neutral-300">
                  {selectedIncident.evidence.map((item, index) => (
                    <li key={index} className="border-b border-neutral-800/60 pb-2">
                      {item}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-neutral-500">No evidence available.</p>
              )}
            </div>

            <div className="bg-neutral-900 rounded-lg p-7">
              <h2 className="text-sm uppercase tracking-wide text-neutral-500 mb-4">
                Recommended Action
              </h2>
              {selectedIncident?.proposedActions?.length ? (
                <div className="space-y-3">
                  {selectedIncident.proposedActions.map((action) => (
                    <div key={action.id} className="border border-neutral-800 rounded-lg p-4">
                      <div className="flex items-start justify-between gap-6">
                        <div>
                          <p className="text-sm font-semibold text-neutral-100">{action.title}</p>
                          <p className="text-sm text-neutral-400 mt-2">{action.description}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs uppercase tracking-wide text-neutral-500">Risk</p>
                          <p className="text-sm text-neutral-300 mt-1">
                            {action.riskLevel.toUpperCase()}
                          </p>
                          <p className="text-xs uppercase tracking-wide text-neutral-500 mt-3">
                            Est. Time
                          </p>
                          <p className="text-sm text-neutral-300 mt-1">{action.estimatedTime}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-neutral-500">No action proposed yet.</p>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-neutral-900 rounded-lg p-6">
              <h2 className="text-sm uppercase tracking-wide text-neutral-500 mb-4">
                Stage Updates
              </h2>
              {selectedIncident?.confidenceEvolution?.length ? (
                <div className="space-y-3">
                  {selectedIncident.confidenceEvolution
                    .slice()
                    .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
                    .map((entry, index) => (
                      <div key={`${entry.stage}-${index}`} className="border-b border-neutral-800/60 pb-3">
                        <p className="text-xs uppercase tracking-wide text-neutral-500">
                          Stage {entry.stage}
                        </p>
                        <p className="text-sm text-neutral-200 mt-1">{entry.description}</p>
                        <p className="text-xs text-neutral-600 mt-2">
                          Confidence: {Math.round(entry.confidence)}%
                        </p>
                      </div>
                    ))}
                </div>
              ) : (
                <p className="text-sm text-neutral-500">No stage updates recorded.</p>
              )}
            </div>

            <div className="bg-neutral-900 rounded-lg p-6">
              <h2 className="text-sm uppercase tracking-wide text-neutral-500 mb-4">
                Incident Queue
              </h2>
              <div className="space-y-2">
                {(incidents && incidents.length > 0 ? incidents : mockIncidents).map((incident) => (
                  <button
                    key={incident.id}
                    onClick={() => setSelectedIncidentId(incident.id)}
                    className={`w-full text-left rounded-lg border px-4 py-3 transition-colors ${
                      incident.id === selectedIncident?.id
                        ? "border-blue-500/40 bg-neutral-800/60"
                        : "border-neutral-800 bg-neutral-900/40 hover:bg-neutral-800/40"
                    }`}
                  >
                    <p className="text-sm font-semibold text-neutral-100">{incident.title}</p>
                    <p className="text-xs text-neutral-500 mt-1">{incident.id}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
