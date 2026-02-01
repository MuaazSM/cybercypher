"use client";

import { Incident } from "@/lib/types";
import { formatConfidence } from "@/lib/utils";
import { AlertCircle, CheckCircle2, Clock } from "lucide-react";

interface IncidentCardProps {
  incident: Incident;
  isPrimary?: boolean;
  onClick?: () => void;
}

export function IncidentCard({ incident, isPrimary = false, onClick }: IncidentCardProps) {
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical":
        return "text-red-500 bg-red-950/30 border-red-900/50";
      case "high":
        return "text-amber-500 bg-amber-950/30 border-amber-900/50";
      default:
        return "text-neutral-500 bg-neutral-800/30 border-neutral-800";
    }
  };

  const topAction = incident.proposedActions[0];
  const timeAgo = Math.round((Date.now() - incident.createdAt.getTime()) / 60000);

  if (!isPrimary) {
    // Compact row for secondary incidents
    return (
      <div
        onClick={onClick}
        className="bg-neutral-900 rounded-lg px-6 py-4 cursor-pointer hover:bg-neutral-900/80 transition-colors"
      >
        <div className="flex items-start justify-between gap-6">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2">
              <h3 className="text-sm font-semibold text-neutral-200 truncate">
                {incident.title}
              </h3>
              <span className={`text-xs font-medium px-2 py-0.5 rounded border ${getSeverityColor(incident.severity)}`}>
                {incident.severity.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-neutral-500 line-clamp-1 leading-relaxed">
              {incident.description}
            </p>
          </div>
          <span className="text-xs text-neutral-600 whitespace-nowrap">{timeAgo}m</span>
        </div>
      </div>
    );
  }

  // Primary incident card - Large and authoritative
  return (
    <div
      onClick={onClick}
      className="bg-neutral-900 rounded-lg p-7 cursor-pointer hover:bg-neutral-900/80 transition-colors min-h-[300px]"
    >
      {/* Header with severity badge */}
      <div className="flex items-start justify-between gap-6 mb-6">
        <div className="flex-1 min-w-0">
          <h3 className="text-xl font-semibold text-neutral-100 mb-3 leading-tight">
            {incident.title}
          </h3>
          <p className="text-sm text-neutral-400 leading-relaxed">
            {incident.description}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className={`text-sm font-semibold px-3 py-1.5 rounded border ${getSeverityColor(incident.severity)}`}>
            {incident.severity.toUpperCase()}
          </span>
          <span className="text-xs text-neutral-600">{timeAgo}m ago</span>
        </div>
      </div>

      {/* Confidence prominently displayed */}
      <div className="mb-6 pb-6 border-b border-neutral-800/50">
        <div className="flex items-baseline gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">Confidence</p>
            <p className="text-3xl font-bold text-neutral-100">{formatConfidence(incident.confidence)}</p>
          </div>
          <div className="ml-8">
            <p className="text-xs uppercase tracking-wide text-neutral-500 mb-1">Status</p>
            <p className="text-sm font-medium text-neutral-300">{incident.status.replace(/([A-Z])/g, ' $1').trim()}</p>
          </div>
        </div>
      </div>

      {/* Evidence as vertical list with icons */}
      <div className="mb-6">
        <p className="text-xs uppercase tracking-wide text-neutral-500 mb-3">Evidence</p>
        <ul className="space-y-2.5">
          {incident.evidence.slice(0, 3).map((evidence, idx) => (
            <li key={idx} className="flex gap-3 text-sm text-neutral-300 leading-relaxed">
              <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
              <span className="flex-1">{evidence}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Recommended Action Panel */}
      {topAction && (
        <div className="bg-neutral-800/40 rounded-lg p-6 border border-neutral-800/50">
          <p className="text-xs uppercase tracking-wide text-neutral-500 mb-3">Recommended Action</p>
          <p className="text-base font-semibold text-neutral-100 mb-2">{topAction.title}</p>
          <p className="text-sm text-neutral-400 leading-relaxed mb-4">{topAction.description}</p>
          <div className="flex gap-6 text-xs">
            <div>
              <span className="text-neutral-500">Success Rate</span>
              <p className="text-sm font-semibold text-neutral-200 mt-0.5">{formatConfidence(topAction.successRate)}</p>
            </div>
            <div>
              <span className="text-neutral-500">Est. Time</span>
              <p className="text-sm font-semibold text-neutral-200 mt-0.5">{topAction.estimatedTime}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
