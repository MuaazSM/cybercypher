"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface TopbarProps {
  title: string;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export function Topbar({ title, onRefresh, isLoading = false }: TopbarProps) {
  const [backendStatus, setBackendStatus] = useState<"online" | "offline" | "checking">("checking");

  useEffect(() => {
    const checkBackend = async () => {
      try {
        await api.healthCheck();
        setBackendStatus("online");
      } catch (error) {
        setBackendStatus("offline");
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="fixed top-0 left-64 right-0 h-16 bg-neutral-900/80 backdrop-blur-sm border-b border-neutral-800/50 flex items-center justify-between px-8 z-40">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-semibold text-neutral-100">{title}</h1>
        {/* Backend Status Indicator */}
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            backendStatus === "online" ? "bg-green-500" :
            backendStatus === "offline" ? "bg-red-500" :
            "bg-yellow-500 animate-pulse"
          }`} />
          <span className="text-xs text-neutral-500">
            {backendStatus === "online" ? "Live" :
             backendStatus === "offline" ? "Mock Data" :
             "Connecting..."}
          </span>
        </div>
      </div>
      {onRefresh && (
        <Button
          onClick={onRefresh}
          variant="ghost"
          size="sm"
          className="text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
          disabled={isLoading}
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      )}
    </div>
  );
}
