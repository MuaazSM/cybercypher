"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Approval } from "@/lib/types";
import {
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  TrendingUp,
  Copy,
  Check,
} from "lucide-react";

interface ApprovalDialogProps {
  approval: Approval | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApprove?: () => void;
  onReject?: () => void;
}

export function ApprovalDialog({
  approval,
  open,
  onOpenChange,
  onApprove,
  onReject,
}: ApprovalDialogProps) {
  const [copied, setCopied] = useState(false);

  if (!approval) return null;

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-neutral-900 border-neutral-800 text-neutral-100">
        {/* Header */}
        <div className="pb-4 border-b border-neutral-800">
          <DialogTitle className="text-base font-semibold text-neutral-100">{approval.title}</DialogTitle>
          <DialogDescription className="text-xs text-neutral-500 mt-1">
            {approval.description}
          </DialogDescription>
        </div>

        {/* Content */}
        <div className="space-y-4 max-h-[60vh] overflow-y-auto">
          {/* Impact */}
          <div>
            <h4 className="text-xs font-medium text-neutral-400 mb-2">Impact</h4>
            <p className="text-sm text-neutral-300">{approval.impact}</p>
          </div>

          {/* Policy Checks */}
          <div>
            <h4 className="text-xs font-medium text-neutral-400 mb-2">
              Policy Checks ({approval.policyChecks.filter((c) => c.passed).length}/
              {approval.policyChecks.length})
            </h4>
            <div className="space-y-1.5">
              {approval.policyChecks.map((check: any, idx: number) => (
                <div
                  key={idx}
                  className={`text-xs p-2 rounded ${
                    check.passed
                      ? "bg-green-950/30 text-green-400"
                      : "bg-red-950/30 text-red-400"
                  }`}
                >
                  <p className="font-medium">{check.name}</p>
                  <p className="text-neutral-500 mt-0.5">{check.description}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Side Effects */}
          {approval.sideEffects.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-neutral-400 mb-2">Side Effects</h4>
              <div className="space-y-1">
                {approval.sideEffects.map((effect: string, idx: number) => (
                  <p key={idx} className="text-xs text-amber-400 bg-amber-950/20 p-2 rounded">
                    {effect}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* Evidence */}
          <div>
            <h4 className="text-xs font-medium text-neutral-400 mb-2">Evidence</h4>
            <ul className="space-y-1 text-xs text-neutral-400">
              {approval.evidence.map((evidence: string, idx: number) => (
                <li key={idx} className="flex gap-2">
                  <span className="text-neutral-600 flex-shrink-0">•</span>
                  <span>{evidence}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Draft Message */}
          <div>
            <h4 className="text-xs font-medium text-neutral-400 mb-2">Draft Message</h4>
            <div className="relative">
              <p className="text-xs text-neutral-300 bg-neutral-950/50 p-3 rounded border border-neutral-800 pr-8">
                {approval.proposedMessage}
              </p>
              <button
                onClick={() => copyToClipboard(approval.proposedMessage)}
                className="absolute top-2 right-2 p-1 hover:bg-neutral-800 rounded transition-colors"
                title="Copy to clipboard"
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-green-500" />
                ) : (
                  <Copy className="w-3.5 h-3.5 text-neutral-500" />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Actions - Decision CTA Dominant */}
        <div className="flex gap-2 pt-4 border-t border-neutral-800">
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            className="flex-1 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-300"
          >
            Cancel
          </Button>
          <Button
            onClick={onReject}
            variant="ghost"
            className="flex-1 text-red-400 hover:bg-red-950/30 hover:text-red-300"
          >
            Reject
          </Button>
          <Button
            onClick={onApprove}
            className="flex-1 bg-green-600 hover:bg-green-700 text-white"
          >
            Approve
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
