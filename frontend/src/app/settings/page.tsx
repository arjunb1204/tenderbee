"use client";

import React, { useState } from "react";
import Image from "next/image";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";

import { apiClient, UserProfile } from "@/lib/api";

export default function SettingsPage() {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [activeTab, setActiveTab] = useState<"profile" | "portals" | "audit" | "notifications" | "team">("profile");
  const [isSaved, setIsSaved] = useState<boolean>(false);

  // Form State
  const [companyName, setCompanyName] = useState("ABC Facility Services Pvt. Ltd.");
  const [udyamNo, setUdyamNo] = useState("UDYAM-DL-08-0098412");
  const [gstin, setGstin] = useState("07AABCT8812K1Z9");
  const [pan, setPan] = useState("AABCT8812K");
  const [vendorClass, setVendorClass] = useState("Class 1 Local Supplier (≥50% Local Content)");
  const [annualTurnover, setAnnualTurnover] = useState("₹8.40 Crore (Average of last 3 FY)");

  // Toggle states
  const [gemSyncEnabled, setGemSyncEnabled] = useState(true);
  const [cpppSyncEnabled, setCpppSyncEnabled] = useState(true);
  const [irepsSyncEnabled, setIrepsSyncEnabled] = useState(true);
  const [autoReAuditCorrigendum, setAutoReAuditCorrigendum] = useState(true);
  const [udinVerificationStrict, setUdinVerificationStrict] = useState(true);
  const [smsUrgentAlerts, setSmsUrgentAlerts] = useState(true);

  React.useEffect(() => {
    apiClient.auth.me().then((user) => {
      setCurrentUser(user);
      if (user.organization) {
        if (user.organization.name) setCompanyName(user.organization.name);
        if (user.organization.gstin) setGstin(user.organization.gstin);
        if (user.organization.udyam_number) setUdyamNo(user.organization.udyam_number);
        if (user.organization.pan) setPan(user.organization.pan);
      }
    }).catch(() => {});
  }, []);

  const isOwner = currentUser?.role === "owner" || currentUser?.role === "admin";

  const handleSave = () => {
    if (!isOwner) return;
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3500);
  };

  return (
    <div className="bg-surface font-sans text-on-surface antialiased min-h-screen">
      {/* Sidebar */}
      <Sidebar activeTab="settings" />

      {/* Main Workspace */}
      <div className="lg:pl-72 flex flex-col min-h-screen">
        {/* Top Header */}
        <DashboardHeader />

        {/* Content Container */}
        <main className="w-full pt-16 bg-surface min-h-screen">
          <div className="px-4 sm:px-8 xl:px-12 py-8 flex flex-col gap-6 max-w-[1500px] mx-auto w-full pb-24">
            {/* Header Strip */}
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[#480870]">settings</span>
                <h1 className="font-serif text-2xl font-bold tracking-tight text-[#1e1b18] sm:text-3xl">
                  Enterprise Settings & Compliance
                </h1>
              </div>
              <p className="mt-1 text-sm text-[#735368]">
                Manage entity profile, GeM / CPPP portal API credentials, DSC tokens, and automated audit thresholds.
              </p>
            </div>

            <button
              type="button"
              onClick={handleSave}
              disabled={!isOwner}
              className="flex items-center gap-2 rounded-xl neu-button-primary px-5 py-2.5 text-xs font-semibold cursor-pointer disabled:opacity-40"
              title={!isOwner ? "Only Organization Owners can save settings" : "Save Preferences"}
            >
              <span className="material-symbols-outlined text-sm">save</span>
              Save Preferences
            </button>
          </div>

          {/* Role restriction alert for non-owners */}
          {currentUser && !isOwner && (
            <div className="mb-6 flex items-center gap-3 rounded-xl neu-flat bg-amber-50/80 p-4 text-amber-900 border border-amber-200 text-xs">
              <span className="material-symbols-outlined text-amber-600 text-base">shield_person</span>
              <span>
                Role: <strong className="uppercase font-bold">{currentUser.role}</strong>. You have read-only permissions for organization settings. Modifying profile or team members requires the <strong>Owner</strong> role.
              </span>
            </div>
          )}

          {/* Save feedback banner */}
          {isSaved && (
            <div className="mb-6 flex items-center justify-between rounded-xl neu-flat bg-emerald-50/90 p-4 text-emerald-900 transition">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-emerald-600">check_circle</span>
                <p className="text-sm font-semibold">Settings and portal sync parameters saved successfully!</p>
              </div>
              <span className="material-symbols-outlined cursor-pointer text-emerald-700" onClick={() => setIsSaved(false)}>
                close
              </span>
            </div>
          )}

          {/* Settings Tabs */}
          <div className="mb-6 flex flex-wrap items-center gap-2.5 border-b border-white/60 pb-4">
            <button
              type="button"
              onClick={() => setActiveTab("profile")}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition cursor-pointer ${
                activeTab === "profile"
                  ? "neu-button-primary"
                  : "neu-button text-on-surface-variant"
              }`}
            >
              <span className="material-symbols-outlined text-sm">business</span>
              Entity & Vendor Profile
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("portals")}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition cursor-pointer ${
                activeTab === "portals"
                  ? "neu-button-primary"
                  : "neu-button text-on-surface-variant"
              }`}
            >
              <span className="material-symbols-outlined text-sm">hub</span>
              Portal Sync & DSC Tokens
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("audit")}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition cursor-pointer ${
                activeTab === "audit"
                  ? "neu-button-primary"
                  : "neu-button text-on-surface-variant"
              }`}
            >
              <span className="material-symbols-outlined text-sm">verified_user</span>
              AI Audit Engine Rules
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("notifications")}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition cursor-pointer ${
                activeTab === "notifications"
                  ? "neu-button-primary"
                  : "neu-button text-on-surface-variant"
              }`}
            >
              <span className="material-symbols-outlined text-sm">notifications</span>
              Alerts & Notifications
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("team")}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition cursor-pointer ${
                activeTab === "team"
                  ? "neu-button-primary"
                  : "neu-button text-on-surface-variant"
              }`}
            >
              <span className="material-symbols-outlined text-sm">group</span>
              Team & RBAC
            </button>
          </div>

          {/* TAB 1: Profile */}
          {activeTab === "profile" && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-[#E9DFE4] bg-white p-6 shadow-xs">
                <div className="flex items-center gap-4 border-b border-[#E9DFE4] pb-6">
                  <div className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-[#EAE0EB] p-2">
                    <Image
                      src="/logo.png"
                      alt="TenderBee Official Logo"
                      width={48}
                      height={48}
                      className="h-10 w-10 object-contain"
                    />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-[#1e1b18]">{companyName}</h2>
                    <p className="text-xs text-[#735368]">
                      Primary Bidder Organization • Verified MSME & Class 1 Supplier
                    </p>
                    <span className="mt-1 inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
                      <span className="material-symbols-outlined text-xs">verified</span>
                      MSME Verified on 14 Aug 2024
                    </span>
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2">
                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-[#735368]">
                      Legal Entity Name
                    </label>
                    <input
                      type="text"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      className="mt-1.5 w-full rounded-xl border border-[#E9DFE4] bg-[#FAF5F8] px-4 py-2.5 text-xs font-semibold text-[#1e1b18] outline-none transition focus:border-[#480870] focus:bg-white"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-[#735368]">
                      UDYAM Registration No.
                    </label>
                    <input
                      type="text"
                      value={udyamNo}
                      onChange={(e) => setUdyamNo(e.target.value)}
                      className="mt-1.5 w-full rounded-xl border border-[#E9DFE4] bg-[#FAF5F8] px-4 py-2.5 font-mono text-xs font-semibold text-[#1e1b18] outline-none transition focus:border-[#480870] focus:bg-white"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-[#735368]">
                      GSTIN (Delhi State)
                    </label>
                    <input
                      type="text"
                      value={gstin}
                      onChange={(e) => setGstin(e.target.value)}
                      className="mt-1.5 w-full rounded-xl border border-[#E9DFE4] bg-[#FAF5F8] px-4 py-2.5 font-mono text-xs font-semibold text-[#1e1b18] outline-none transition focus:border-[#480870] focus:bg-white"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-[#735368]">
                      PAN (Permanent Account No.)
                    </label>
                    <input
                      type="text"
                      value={pan}
                      onChange={(e) => setPan(e.target.value)}
                      className="mt-1.5 w-full rounded-xl border border-[#E9DFE4] bg-[#FAF5F8] px-4 py-2.5 font-mono text-xs font-semibold text-[#1e1b18] outline-none transition focus:border-[#480870] focus:bg-white"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-[#735368]">
                      Local Content Category (PPP-MII 2017)
                    </label>
                    <input
                      type="text"
                      value={vendorClass}
                      onChange={(e) => setVendorClass(e.target.value)}
                      className="mt-1.5 w-full rounded-xl border border-[#E9DFE4] bg-[#FAF5F8] px-4 py-2.5 text-xs font-semibold text-[#1e1b18] outline-none transition focus:border-[#480870] focus:bg-white"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-[#735368]">
                      Audited Average Annual Turnover
                    </label>
                    <input
                      type="text"
                      value={annualTurnover}
                      onChange={(e) => setAnnualTurnover(e.target.value)}
                      className="mt-1.5 w-full rounded-xl border border-[#E9DFE4] bg-[#FAF5F8] px-4 py-2.5 text-xs font-semibold text-[#1e1b18] outline-none transition focus:border-[#480870] focus:bg-white"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Portals */}
          {activeTab === "portals" && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-[#E9DFE4] bg-white p-6 shadow-xs">
                <h2 className="text-base font-bold text-[#1e1b18]">Connected E-Procurement Portals</h2>
                <p className="mt-1 text-xs text-[#735368]">
                  Automated background synchronizers ingest tenders, corrigenda, and upload verified bid envelopes.
                </p>

                <div className="mt-6 space-y-4">
                  {/* GeM */}
                  <div className="flex items-center justify-between rounded-xl border border-[#E9DFE4] p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-100 text-orange-700 font-bold text-xs">
                        GeM
                      </div>
                      <div>
                        <p className="font-semibold text-xs text-[#1e1b18]">Government e-Marketplace (GeM 4.0)</p>
                        <p className="text-[11px] text-[#735368]">Seller ID: GEM-DL-984210 • Synced 14m ago</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setGemSyncEnabled(!gemSyncEnabled)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                        gemSyncEnabled ? "bg-[#480870]" : "bg-neutral-300"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                          gemSyncEnabled ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>

                  {/* CPPP */}
                  <div className="flex items-center justify-between rounded-xl border border-[#E9DFE4] p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-700 font-bold text-xs">
                        CPPP
                      </div>
                      <div>
                        <p className="font-semibold text-xs text-[#1e1b18]">Central Public Procurement Portal (NIC)</p>
                        <p className="text-[11px] text-[#735368]">eProcure ID: ABC_FACILITY • Live Webhook active</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setCpppSyncEnabled(!cpppSyncEnabled)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                        cpppSyncEnabled ? "bg-[#480870]" : "bg-neutral-300"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                          cpppSyncEnabled ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>

                  {/* IREPS */}
                  <div className="flex items-center justify-between rounded-xl border border-[#E9DFE4] p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 font-bold text-xs">
                        IREPS
                      </div>
                      <div>
                        <p className="font-semibold text-xs text-[#1e1b18]">Indian Railways E-Procurement System</p>
                        <p className="text-[11px] text-[#735368]">CRIS Registered Vendor ID: VEN-991204</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setIrepsSyncEnabled(!irepsSyncEnabled)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                        irepsSyncEnabled ? "bg-[#480870]" : "bg-neutral-300"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                          irepsSyncEnabled ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Audit Rules */}
          {activeTab === "audit" && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-[#E9DFE4] bg-white p-6 shadow-xs">
                <h2 className="text-base font-bold text-[#1e1b18]">AI Verification Engine Thresholds</h2>
                <p className="mt-1 text-xs text-[#735368]">
                  Define how rigorously TenderBee flags risks, EMD omissions, and UDIN cross-checks.
                </p>

                <div className="mt-6 space-y-5">
                  <div className="flex items-center justify-between border-b border-[#E9DFE4] pb-4">
                    <div>
                      <p className="text-xs font-bold text-[#1e1b18]">Mandatory UDIN Live Verification</p>
                      <p className="text-[11px] text-[#735368]">
                        Fail audit if Chartered Accountant turnover certificate lacks active ICAI UDIN number.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setUdinVerificationStrict(!udinVerificationStrict)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                        udinVerificationStrict ? "bg-[#480870]" : "bg-neutral-300"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                          udinVerificationStrict ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>

                  <div className="flex items-center justify-between border-b border-[#E9DFE4] pb-4">
                    <div>
                      <p className="text-xs font-bold text-[#1e1b18]">Auto Re-Audit on Corrigendum Release</p>
                      <p className="text-[11px] text-[#735368]">
                        Immediately trigger autonomous document re-audit when tender issuing department publishes an amendment.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setAutoReAuditCorrigendum(!autoReAuditCorrigendum)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                        autoReAuditCorrigendum ? "bg-[#480870]" : "bg-neutral-300"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                          autoReAuditCorrigendum ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: Notifications */}
          {activeTab === "notifications" && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-[#E9DFE4] bg-white p-6 shadow-xs">
                <h2 className="text-base font-bold text-[#1e1b18]">Alert Channels & Delivery Preferences</h2>
                <p className="mt-1 text-xs text-[#735368]">
                  Receive notifications before critical deadlines and upon portal amendments.
                </p>

                <div className="mt-6 space-y-4">
                  <div className="flex items-center justify-between border-b border-[#E9DFE4] pb-4">
                    <div>
                      <p className="text-xs font-bold text-[#1e1b18]">Instant SMS & WhatsApp for Critical Corrigenda</p>
                      <p className="text-[11px] text-[#735368]">Send high-priority SMS when submission deadline changes.</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSmsUrgentAlerts(!smsUrgentAlerts)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                        smsUrgentAlerts ? "bg-[#480870]" : "bg-neutral-300"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                          smsUrgentAlerts ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: Team */}
          {activeTab === "team" && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-[#E9DFE4] bg-white p-6 shadow-xs">
                <div className="flex items-center justify-between border-b border-[#E9DFE4] pb-4">
                  <div>
                    <h2 className="text-base font-bold text-[#1e1b18]">Team Members & Access Levels</h2>
                    <p className="mt-1 text-xs text-[#735368]">
                      Manage who can attach DSC signatures, approve technical bids, and view financial envelopes.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="flex items-center gap-1.5 rounded-lg bg-[#480870] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#3B0066]"
                  >
                    <span className="material-symbols-outlined text-sm">person_add</span>
                    Invite Member
                  </button>
                </div>

                <div className="mt-4 divide-y divide-[#E9DFE4]">
                  <div className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#EAE0EB] font-bold text-xs text-[#480870]">
                        RD
                      </div>
                      <div>
                        <p className="text-xs font-bold text-[#1e1b18]">Rajesh Duggal</p>
                        <p className="text-[11px] text-[#735368]">Managing Director & DSC Token Holder</p>
                      </div>
                    </div>
                    <span className="rounded-md bg-purple-100 px-2.5 py-1 text-[11px] font-semibold text-[#480870]">
                      Super Admin (DSC Signing)
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 font-bold text-xs text-indigo-700">
                        AK
                      </div>
                      <div>
                        <p className="text-xs font-bold text-[#1e1b18]">Ananya Kapoor</p>
                        <p className="text-[11px] text-[#735368]">Head of Tenders & Government Bidding</p>
                      </div>
                    </div>
                    <span className="rounded-md bg-indigo-100 px-2.5 py-1 text-[11px] font-semibold text-indigo-800">
                      Bid Manager
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 font-bold text-xs text-emerald-700">
                        VM
                      </div>
                      <div>
                        <p className="text-xs font-bold text-[#1e1b18]">Vikram Malhotra, FCA</p>
                        <p className="text-[11px] text-[#735368]">External Statutory Chartered Accountant</p>
                      </div>
                    </div>
                    <span className="rounded-md bg-emerald-100 px-2.5 py-1 text-[11px] font-semibold text-emerald-800">
                      UDIN & Financial Auditor
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  </div>
  );
}
