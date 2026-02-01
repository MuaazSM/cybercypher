// src/app/activity/page.tsx
"use client";

import { Topbar } from "@/components/Topbar";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { mockActivity } from "@/lib/mock";
import { usePolling } from "@/lib/usePolling";
import {
  AlertTriangle,
  CheckCircle,
  FileText,
  Clock,
  ArrowRight,
} from "lucide-react";

export default function ActivityPage() {
  const { data: activities, refetch: refreshActivity } = usePolling(
    async () => mockActivity,
    { interval: 5000 }
  );

  const getActivityIcon = (type: string) => {
    switch (type) {
      case "alert":
        return <AlertTriangle className="w-4 h-4 text-red-400" />;
      case "evidence":
        return <FileText className="w-4 h-4 text-blue-400" />;
      case "action":
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case "decision":
        return <ArrowRight className="w-4 h-4 text-purple-400" />;
      case "escalation":
        return <AlertTriangle className="w-4 h-4 text-amber-400" />;
      default:
        return <Clock className="w-4 h-4 text-neutral-400" />;
    }
  };

  const getActivityBadgeColor = (type: string) => {
    switch (type) {
      case "alert":
        return "bg-red-500/20 text-red-200";
      case "evidence":
        return "bg-blue-500/20 text-blue-200";
      case "action":
        return "bg-green-500/20 text-green-200";
      case "decision":
        return "bg-purple-500/20 text-purple-200";
      case "escalation":
        return "bg-amber-500/20 text-amber-200";
      default:
        return "bg-neutral-500/20 text-neutral-200";
    }
  };

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

  const formatType = (type: string) => {
    return type
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  return (
    <div className="min-h-screen pt-16 pb-8">
      <Topbar title="Activity" onRefresh={refreshActivity} />

      <main className="max-w-7xl mx-auto px-8 space-y-6">
        <Card className="bg-neutral-900/40 border-neutral-800 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="border-neutral-800/50 bg-neutral-900/20 hover:bg-neutral-900/20">
                <TableHead className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">Type</TableHead>
                <TableHead className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">Title</TableHead>
                <TableHead className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">Description</TableHead>
                <TableHead className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">Confidence</TableHead>
                <TableHead className="text-xs font-semibold text-neutral-500 uppercase tracking-wider text-right">Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activities?.map((activity) => (
                <TableRow
                  key={activity.id}
                  className="border-neutral-800/50 hover:bg-neutral-800/10 transition-colors h-12"
                >
                  <TableCell className="py-2">
                    <div className="flex items-center gap-2">
                      {getActivityIcon(activity.type)}
                      <Badge className={getActivityBadgeColor(activity.type)} variant="secondary">
                        {activity.type}
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell className="font-medium text-neutral-100 py-2 text-sm">
                    {activity.title}
                  </TableCell>
                  <TableCell className="text-neutral-400 max-w-sm truncate py-2 text-sm">
                    {activity.description}
                  </TableCell>
                  <TableCell className="py-2 text-sm">
                    {activity.confidence ? (
                      <span className="text-neutral-300 font-medium">
                        {Math.round(activity.confidence * 100)}%
                      </span>
                    ) : (
                      <span className="text-neutral-600">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-neutral-500 text-right text-sm py-2">
                    {formatTime(activity.timestamp)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </main>
    </div>
  );
}
