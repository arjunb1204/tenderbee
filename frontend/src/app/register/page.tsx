"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { apiClient } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();

  const [orgName, setOrgName] = useState("");
  const [gstin, setGstin] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");

    if (!orgName.trim()) {
      setErrorMessage("Organization legal name is required.");
      return;
    }
    if (!email || !email.includes("@")) {
      setErrorMessage("Please enter a valid work email address.");
      return;
    }
    if (!password || password.length < 8) {
      setErrorMessage("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const res = await apiClient.auth.register({
        organization_name: orgName.trim(),
        gstin: gstin.trim() || undefined,
        username: username.trim() || undefined,
        email: email.trim().toLowerCase(),
        password,
      });

      if (res.success) {
        router.push("/dashboard");
        router.refresh();
      } else {
        setErrorMessage("Registration could not be completed.");
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Registration failed. Please check your information.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative overflow-hidden flex items-center justify-center px-4 py-12 bg-[#edf1f7]">
      {/* Ambient glowing backdrop elements */}
      <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-400/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-400/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] bg-amber-100/25 rounded-full blur-[120px] pointer-events-none" />

      {/* Main Container */}
      <div className="relative w-full max-w-xl">
        {/* Top Navigation Row */}
        <div className="mb-6 flex items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-purple-700 transition-colors group"
          >
            <svg className="w-4 h-4 transition-transform group-hover:-translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            <span>Back to Home</span>
          </Link>

          <span className="text-[11px] font-medium tracking-wide uppercase px-2.5 py-1 rounded-full bg-emerald-100/80 text-emerald-800 border border-emerald-200/50 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Multi-Tenant Onboarding
          </span>
        </div>

        {/* Signup Card */}
        <div className="rounded-3xl p-8 sm:p-10 neu-flat backdrop-blur-sm relative overflow-hidden border border-white/80 shadow-2xl">
          {/* Subtle top accent gradient */}
          <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-indigo-600 via-purple-600 to-amber-500" />

          {/* Header & Logo */}
          <div className="text-center mb-8">
            <Link href="/" className="inline-block group">
              <div className="w-20 h-20 mx-auto mb-4 rounded-2xl p-2 neu-flat-sm bg-white/90 flex items-center justify-center group-hover:scale-105 transition-transform duration-300">
                <Image
                  src="/logo.png"
                  alt="TenderBee Official Logo"
                  width={68}
                  height={68}
                  className="w-full h-full object-contain scale-[1.25]"
                  priority
                />
              </div>
            </Link>

            <h1 className="font-serif text-3xl font-bold tracking-tight text-slate-900">
              Create <span className="bg-gradient-to-r from-purple-700 to-indigo-600 bg-clip-text text-transparent">Tenant Workspace</span>
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 mt-2 font-medium">
              Set up your organization and unlock deterministic tender intake & AI verification
            </p>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="mb-6 p-4 rounded-2xl border border-rose-200/80 bg-rose-50/80 text-rose-700 text-xs sm:text-sm flex items-start gap-3 shadow-sm animate-shake">
              <svg className="w-5 h-5 shrink-0 text-rose-500 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <span className="leading-snug">{errorMessage}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5">
            {/* Organization Name */}
            <div>
              <label htmlFor="register-org" className="block text-xs font-semibold tracking-wider text-slate-700 mb-1.5 uppercase">
                Company / Organization Legal Name *
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                </div>
                <input
                  id="register-org"
                  type="text"
                  required
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="e.g. Bharat Infrastructure & Defence Ltd."
                  className="w-full pl-10 pr-4 py-3 rounded-xl neu-inset bg-[#edf1f7] text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-600/40 text-sm transition-all placeholder:text-slate-400"
                  disabled={loading}
                />
              </div>
            </div>

            {/* GSTIN & Full Name Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="register-gstin" className="block text-xs font-semibold tracking-wider text-slate-700 mb-1.5 uppercase">
                  GSTIN <span className="text-[10px] text-slate-400 font-normal lowercase">(optional)</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <input
                    id="register-gstin"
                    type="text"
                    value={gstin}
                    onChange={(e) => setGstin(e.target.value.toUpperCase())}
                    placeholder="27AAAAA0000A1Z5"
                    maxLength={15}
                    className="w-full pl-10 pr-4 py-3 rounded-xl neu-inset bg-[#edf1f7] text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-600/40 text-sm transition-all placeholder:text-slate-400 font-mono text-xs uppercase"
                    disabled={loading}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="register-username" className="block text-xs font-semibold tracking-wider text-slate-700 mb-1.5 uppercase">
                  Full Name / Admin Name
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                  <input
                    id="register-username"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Aditya Sharma"
                    className="w-full pl-10 pr-4 py-3 rounded-xl neu-inset bg-[#edf1f7] text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-600/40 text-sm transition-all placeholder:text-slate-400"
                    disabled={loading}
                  />
                </div>
              </div>
            </div>

            {/* Work Email Address */}
            <div>
              <label htmlFor="register-email" className="block text-xs font-semibold tracking-wider text-slate-700 mb-1.5 uppercase">
                Work Email Address *
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </div>
                <input
                  id="register-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="director@bharat-infra.in"
                  className="w-full pl-10 pr-4 py-3 rounded-xl neu-inset bg-[#edf1f7] text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-600/40 text-sm transition-all placeholder:text-slate-400"
                  disabled={loading}
                />
              </div>
            </div>

            {/* Password & Confirm Password Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="register-password" className="block text-xs font-semibold tracking-wider text-slate-700 mb-1.5 uppercase">
                  Password *
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  </div>
                  <input
                    id="register-password"
                    type={showPassword ? "text" : "password"}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min 8 characters"
                    className="w-full pl-10 pr-10 py-3 rounded-xl neu-inset bg-[#edf1f7] text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-600/40 text-sm transition-all placeholder:text-slate-400"
                    disabled={loading}
                  />
                  <button
                    type="button"
                    id="toggle-register-password"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1 focus:outline-none cursor-pointer transition-colors"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <div>
                <label htmlFor="register-confirm-password" className="block text-xs font-semibold tracking-wider text-slate-700 mb-1.5 uppercase">
                  Confirm Password *
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  </div>
                  <input
                    id="register-confirm-password"
                    type={showConfirmPassword ? "text" : "password"}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat password"
                    className="w-full pl-10 pr-10 py-3 rounded-xl neu-inset bg-[#edf1f7] text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-600/40 text-sm transition-all placeholder:text-slate-400"
                    disabled={loading}
                  />
                  <button
                    type="button"
                    id="toggle-register-confirm-password"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1 focus:outline-none cursor-pointer transition-colors"
                    aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                  >
                    {showConfirmPassword ? (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Primary Submit Button */}
            <button
              type="submit"
              id="register-submit-btn"
              disabled={loading}
              className="w-full mt-3 py-3.5 px-6 rounded-xl font-semibold text-sm transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer bg-gradient-to-r from-purple-700 via-indigo-700 to-purple-800 text-white shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 hover:scale-[1.01] active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                  </svg>
                  <span>Provisioning Isolated Workspace...</span>
                </>
              ) : (
                <>
                  <span>Create Workspace & Sign In</span>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </>
              )}
            </button>
          </form>

          {/* Footer Navigation */}
          <div className="mt-8 pt-6 border-t border-slate-200/70 text-center">
            <p className="text-xs text-slate-600">
              Already have an organization workspace?{" "}
              <Link href="/login" className="font-semibold text-purple-700 hover:text-purple-900 hover:underline transition-colors">
                Sign In Instead
              </Link>
            </p>
          </div>
        </div>

        {/* Security Trust Badges */}
        <div className="mt-6 flex items-center justify-center gap-6 text-[11px] font-medium text-slate-500">
          <span className="flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 1.944A11.954 11.954 0 012.166 5C2.056 5.649 2 6.319 2 7c0 5.225 3.34 9.67 8 11.317C14.66 16.67 18 12.225 18 7c0-.682-.057-1.35-.166-2.001A11.954 11.954 0 0110 1.944zm4.293 6.707a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            Zero-Leak Isolation
          </span>
          <span className="w-1 h-1 rounded-full bg-slate-300" />
          <span>Role-Based Access</span>
          <span className="w-1 h-1 rounded-full bg-slate-300" />
          <span>Audit Trail Enabled</span>
        </div>
      </div>
    </div>
  );
}
