// src/app/approvals/page.tsx
"use client";

import { useState } from "react";
import { Topbar } from "@/components/Topbar";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApprovalDialog } from "@/components/ApprovalDialog";
import { mockApprovals } from "@/lib/mock";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { CheckCircle, XCircle, Clock, AlertTriangle } from "lucide-react";

export default function ApprovalsPage() {
  const [selectedApproval, setSelectedApproval] = useState(mockApprovals[0]);
  const [dialogOpen, setDialogOpen] = useState(false);

  // Use real API with fallback to mock data
  const { data: approvals, refetch: refreshApprovals } = usePolling(
    async () => {
      try {
        const data = await api.getPendingApprovals();
        return data.length > 0 ? data : mockApprovals;
      } catch (error) {
        console.error("Failed to fetch approvals:", error);
        return mockApprovals;
      }
    },
    { interval: 5000 }
  );

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pending":
        return <Clock className="w-5 h-5 text-amber-500" />;
      case "approved":
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case "rejected":
        return <XCircle className="w-5 h-5 text-red-500" />;
      case "auto-approved":
        return <CheckCircle className="w-5 h-5 text-blue-500" />;
      default:
        return <Clock className="w-5 h-5 text-neutral-500" />;
    }
  };

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case "pending":
        return "bg-amber-500 text-black";
      case "approved":
        return "bg-green-600 text-white";
      case "rejected":
        return "bg-red-600 text-white";
      case "auto-approved":
        return "bg-blue-600 text-white";
      default:
        return "bg-neutral-600 text-white";
    }
  };

  const handleOpenApproval = (approval: typeof mockApprovals[0]) => {
    setSelectedApproval(approval);
    setDialogOpen(true);
  };

  const handleApprove = async () => {
    if (!selectedApproval) return;
    
    try {
      await api.approveAction(selectedApproval.id, "dashboard-user");
      console.log("Approved:", selectedApproval.id);
      setDialogOpen(false);
      refreshApprovals(); // Refresh the list
    } catch (error) {
      console.error("Failed to approve:", error);
      alert("Failed to approve action. Please try again.");
    }
  };

  const handleReject = async () => {
    if (!selectedApproval) return;
    
    console.log("Rejected:", selectedApproval.id);
    setDialogOpen(false);
    // Note: Backend doesn't have reject endpoint yet
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="min-h-screen pt-16 pb-12">
      <Topbar title="Approvals" onRefresh={refreshApprovals} />

      <main className="max-w-6xl mx-auto px-8 space-y-8">
        <h1 className="text-2xl font-semibold text-neutral-100">Pending Approvals</h1>
        
        {!approvals || approvals.length === 0 ? (
          <div className="bg-neutral-900 rounded-lg p-12 text-center">
            <p className="text-neutral-500 text-sm">No pending approvals</p>
          </div>
        ) : (
          <div className="space-y-4">
            {approvals.map((approval) => {
              const allChecksPassed = approval.policyChecks.every((check) => check.passed);
              const isPending = approval.status === "pending";
              return (
                <div
                  key={approval.id}
                  className="bg-neutral-900 rounded-lg p-7 hover:bg-neutral-900/80 transition-colors min-h-[200px]"
                >
                  <div className="grid grid-cols-3 gap-8">
                    {/* Left: Policy checks and explanation */}
                    <div className="col-span-2">
                      <h3 className="text-lg font-semibold text-neutral-100 mb-2">
                        {approval.title}
                      </h3>
                      <p className="text-sm text-neutral-400 leading-relaxed mb-6">{approval.description}</p>
                      
                      {/* Policy Checks */}
                      <div className="mb-4">
                        <p className="text-xs uppercase tracking-wide text-neutral-500 mb-3">
                          Policy Checks ({approval.policyChecks.filter((c) => c.passed).length}/{approval.policyChecks.length})
                        </p>
                        <div className="space-y-2">
                          {approval.policyChecks.map((check, idx) => (
                            <div
                              key={idx}
                              className="flex items-start gap-3 text-sm"
                            >
                              {check.passed ? (
                                <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                              ) : (
                                <XCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                              )}
                              <div className="flex-1">
                                <p className={check.passed ? "text-neutral-300" : "text-neutral-400"}>
                                  {check.name}
                                </p>
                                <p className="text-xs text-neutral-600 mt-0.5">{check.description}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      {/* Side Effects */}
                      {approval.sideEffects.length > 0 && (
                        <div className="mt-4">
                          <p className="text-xs uppercase tracking-wide text-neutral-500 mb-2">
                            Side Effects ({approval.sideEffects.length})
                          </p>
                          <div className="space-y-1">
                            {approval.sideEffects.map((effect, idx) => (
                              <p key={idx} className="text-xs text-amber-400 flex items-start gap-2">
                                <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                                {effect}
                              </p>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    
                    {/* Right: Action buttons */}
                    <div className="flex flex-col justify-between">
                      <div>
                        <p className="text-xs uppercase tracking-wide text-neutral-500 mb-2">Risk Level</p>
                        <p className="text-sm font-semibold text-neutral-300 mb-4">{approval.riskLevel}</p>
                        <p className="text-xs text-neutral-600">{formatTime(approval.createdAt)}</p>
                      </div>
                      
                      {isPending && (
                        <Button
                          onClick={() => handleOpenApproval(approval)}
                          className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-6 text-base w-full"
                        >
                          Review Action
                        </Button>
                      )}
                      {!isPending && (
                        <div className="text-sm text-neutral-500 capitalize">
                          Status: {approval.status}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Approval Dialog */}
      <ApprovalDialog
        approval={selectedApproval}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onApprove={handleApprove}
        onReject={handleReject}
      />
    </div>
  );
}
