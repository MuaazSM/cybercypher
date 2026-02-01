"use client";

import { Activity } from "@/lib/types";
import { formatConfidence } from "@/lib/utils";

interface ActivityFeedProps {
  activities: Activity[];
}

export function ActivityFeed({ activities }: ActivityFeedProps) {
  const formatTime = (timestamp: Date) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "now";
    if (diffMins < 60) return `${diffMins}m`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h`;
    return date.toLocaleDateString();
  };

  return (
    <div className="divide-y divide-neutral-800/30">
      {activities.map((activity) => (
        <div key={activity.id} className="py-3 hover:bg-neutral-800/20 px-2 -mx-2 rounded transition-colors">
          <div className="flex items-baseline justify-between gap-3 mb-1">
            <p className="text-sm font-medium text-neutral-200">
              {activity.title}
            </p>
            <span className="text-xs text-neutral-600 whitespace-nowrap flex-shrink-0">
              {formatTime(activity.timestamp)}
            </span>
          </div>
          <p className="text-xs text-neutral-500 leading-relaxed line-clamp-1">
            {activity.description}
          </p>
          {activity.confidence && (
            <p className="text-xs text-neutral-600 mt-1">
              {formatConfidence(activity.confidence)} confidence
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
