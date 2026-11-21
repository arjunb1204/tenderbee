"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { apiClient, UserProfile } from "@/lib/api";

export default function DashboardHeader() {
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [headerSearch, setHeaderSearch] = useState("");
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    let isMounted = true;
    apiClient.auth
      .me()
      .then((user) => {
        if (isMounted) setCurrentUser(user);
      })
      .catch(() => {
        // Fallback for demo / offline view
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (headerSearch.trim()) {
      router.push(`/tenders?q=${encodeURIComponent(headerSearch.trim())}`);
    } else {
      router.push("/tenders");
    }
  };

  const handleLogout = async () => {
    try {
      await apiClient.auth.logout();
    } catch {
      // Ignored
    } finally {
      router.push("/login");
      router.refresh();
    }
  };

  return (
    <>
      <header className="fixed top-0 left-0 lg:left-72 right-0 h-16 bg-surface-container-low/90 backdrop-blur-xl z-40 border-b border-white/60 shadow-[0_4px_16px_rgba(162,176,200,0.16)] px-4 sm:px-8 flex items-center justify-between">
        {/* Mobile Brand Toggle */}
        <div className="flex items-center gap-2 lg:hidden">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-xl neu-button text-on-surface cursor-pointer"
            aria-label="Toggle Navigation"
          >
            <span className="material-symbols-outlined text-2xl">menu</span>
          </button>
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg overflow-hidden flex items-center justify-center neu-flat-sm bg-surface-container-lowest">
              <Image src="/logo.png" alt="TenderBee" width={32} height={32} className="w-full h-full object-contain scale-[1.3]" priority />
            </div>
            <span className="font-serif text-xl font-bold text-primary">TenderBee</span>
          </Link>
        </div>

        {/* Global Search Bar - Neumorphic Debossed Field */}
        <form onSubmit={handleSearchSubmit} className="hidden sm:flex items-center gap-4 flex-1 max-w-xl">
          <div className="relative w-full">
            <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg">
              search
            </span>
            <input
              className="w-full pl-10 pr-4 py-2 neu-pressed rounded-xl text-xs sm:text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-1 focus:ring-secondary/40 transition-all"
              placeholder="Search tenders, NITs, docs (⌘K)..."
              type="text"
              value={headerSearch}
              onChange={(e) => setHeaderSearch(e.target.value)}
            />
          </div>
        </form>

        {/* Header Right Cluster */}
        <div className="flex items-center gap-3 sm:gap-4">
          {/* GeM & CPPP Synced Badge */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full neu-flat-sm">
            <div className="w-2 h-2 rounded-full bg-secondary animate-ping" />
            <span className="text-[10px] uppercase tracking-wider font-semibold text-on-surface-variant">
              GeM &amp; CPPP
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-bold">
              Synced
            </span>
          </div>

          {/* Notifications Button */}
          <button
            className="relative p-2 rounded-full neu-button text-on-surface-variant hover:text-on-surface cursor-pointer"
            type="button"
            aria-label="View notifications"
          >
            <span className="material-symbols-outlined text-2xl">notifications</span>
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-secondary" />
          </button>

          <div className="h-6 w-px bg-white/70 shadow-sm hidden sm:block" />

          {/* User Profile & Logout */}
          <div className="flex items-center gap-2">
            <Link href="/settings" className="flex items-center gap-2.5 pl-1 group cursor-pointer">
              <div className="flex flex-col text-right hidden sm:flex">
                <span className="text-xs font-semibold text-on-surface group-hover:text-primary transition-colors leading-tight">
                  {currentUser ? (currentUser.username || currentUser.email.split("@")[0]) : "Loading..."}
                </span>
                <span className="text-[10px] font-semibold text-amber-600 uppercase tracking-wider">
                  {currentUser ? currentUser.role : "Member"} • {currentUser?.organization?.name ? currentUser.organization.name.slice(0, 16) + '...' : "Workspace"}
                </span>
              </div>
              {/* User Avatar */}
              <div className="w-9 h-9 rounded-full neu-flat-sm flex items-center justify-center text-on-secondary-fixed bg-secondary-fixed font-bold text-xs ring-2 ring-white shadow-sm overflow-hidden group-hover:scale-105 transition-all">
                <span className="material-symbols-outlined text-lg">person</span>
              </div>
            </Link>

            <button
              onClick={handleLogout}
              className="p-2 rounded-xl neu-button text-slate-500 hover:text-rose-600 transition-colors ml-1 cursor-pointer"
              title="Sign Out"
              aria-label="Sign Out"
            >
              <span className="material-symbols-outlined text-lg">logout</span>
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="lg:hidden fixed top-16 left-0 right-0 bg-surface-container-lowest border-b border-outline-variant/30 z-50 p-4 shadow-xl">
          <nav className="flex flex-col gap-2">
            <Link
              href="/dashboard"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center gap-3 px-3 py-2 rounded-lg bg-surface-container-high text-on-surface text-sm font-semibold"
            >
              <span className="material-symbols-outlined text-lg">grid_view</span>
              <span>Dashboard</span>
            </Link>
            <Link
              href="/tenders"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-on-surface-variant hover:bg-surface-container text-sm font-medium"
            >
              <span className="material-symbols-outlined text-lg">gavel</span>
              <span>Open Tenders</span>
            </Link>
            <Link
              href="/vault"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-on-surface-variant hover:bg-surface-container text-sm font-medium"
            >
              <span className="material-symbols-outlined text-lg">folder_managed</span>
              <span>Document Vault</span>
            </Link>
            <Link
              href="/audit"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-on-surface-variant hover:bg-surface-container text-sm font-medium"
            >
              <span className="material-symbols-outlined text-lg">verified_user</span>
              <span>Bid Readiness &amp; Audits</span>
            </Link>
            <Link
              href="/corrigendum"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-on-surface-variant hover:bg-surface-container text-sm font-medium"
            >
              <span className="material-symbols-outlined text-lg">radar</span>
              <span>Corrigendum Radar</span>
            </Link>
            <Link
              href="/settings"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-on-surface-variant hover:bg-surface-container text-sm font-medium"
            >
              <span className="material-symbols-outlined text-lg">settings</span>
              <span>Settings</span>
            </Link>
          </nav>
        </div>
      )}
    </>
  );
}
