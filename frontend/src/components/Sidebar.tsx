"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertCircle, Activity, CheckSquare, LayoutDashboard } from "lucide-react";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();

  const links = [
    {
      href: "/",
      label: "Dashboard",
      icon: LayoutDashboard,
      active: pathname === "/",
    },
    {
      href: "/activity",
      label: "Activity Feed",
      icon: Activity,
      active: pathname === "/activity",
    },
    {
      href: "/approvals",
      label: "Approvals",
      icon: CheckSquare,
      active: pathname === "/approvals",
    },
  ];

  return (
    <div className="fixed left-0 top-0 h-screen w-64 bg-neutral-950/80 backdrop-blur border-r border-neutral-800 p-6 flex flex-col z-50">
      {/* Logo */}
      <div className="flex items-center gap-2 mb-8">
        <div className="w-8 h-8 bg-red-600 rounded flex items-center justify-center">
          <AlertCircle className="w-5 h-5 text-white" />
        </div>
        <span className="font-semibold text-base text-neutral-100">CyberCypher</span>
      </div>

      {/* Navigation */}
      <nav className="space-y-1 flex-1">
        {links.map((link) => {
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors",
                link.active
                  ? "bg-neutral-800 text-neutral-100"
                  : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900"
              )}
            >
              <Icon className="w-4 h-4" />
              <span>{link.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer info */}
      <div className="border-t border-neutral-200 pt-4 text-xs text-neutral-600">
        <p className="font-semibold text-neutral-900 mb-1">System</p>
        <p>✓ All operational</p>
        <p className="text-neutral-500 mt-1">Last sync: now</p>
      </div>
    </div>
  );
}
