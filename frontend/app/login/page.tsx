"use client";

import { useState } from "react";

// ReqGuard — Login page
// Location in project: frontend/app/login/page.tsx
// Open at: http://localhost:3000/login

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  function validate() {
    const e: { email?: string; password?: string } = {};
    if (!email.trim()) e.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = "Enter a valid email address.";
    if (!password) e.password = "Password is required.";
    else if (password.length < 8) e.password = "Password must be at least 8 characters.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    setFormError("");
    setSuccess("");
    if (!validate()) return;

    setLoading(true);
    try {
      // TODO: connect to FastAPI backend later, e.g.
      // const res = await fetch("http://127.0.0.1:8000/auth/login", {
      //   method: "POST",
      //   headers: { "Content-Type": "application/json" },
      //   body: JSON.stringify({ email, password }),
      // });
      // if (!res.ok) throw new Error("Invalid email or password.");
      await new Promise((r) => setTimeout(r, 900)); // demo delay
      setSuccess("Login successful (demo mode). Backend connection comes next.");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-zinc-950 text-zinc-100">
      {/* Background: faint grid + two soft colour glows */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)",
        }}
      />
      <div aria-hidden="true" className="pointer-events-none absolute -top-40 -left-40 h-[32rem] w-[32rem] rounded-full bg-indigo-600/30 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-40 -right-32 h-[28rem] w-[28rem] rounded-full bg-amber-500/20 blur-3xl" />

      <div className="relative mx-auto grid min-h-screen max-w-6xl items-center gap-12 px-4 py-12 sm:px-8 lg:grid-cols-2">
        {/* Left: product story */}
        <section className="hidden lg:block">
          <div className="flex items-center gap-3">
            <ShieldIcon />
            <span className="text-xl font-semibold tracking-tight">ReqGuard</span>
          </div>

          <h1 className="mt-10 text-5xl font-semibold leading-[1.1] tracking-tight">
            Know what to verify{" "}
            <span className="bg-linear-to-r from-indigo-300 via-violet-300 to-amber-300 bg-clip-text text-transparent">
              before you release.
            </span>
          </h1>
          <p className="mt-5 max-w-md text-zinc-400">
            Link requirements, code and tests. Catch drift after every change, with evidence you can trace.
          </p>

          <ul className="mt-8 space-y-3 text-sm text-zinc-300">
            {[
              "Tag-free traceability recovered from your repository",
              "Two-way drift detection between requirements and code",
              "Criterion-level test evidence, with test lines quoted",
            ].map((item) => (
              <li key={item} className="flex items-center gap-3">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-300">
                  <CheckIcon />
                </span>
                {item}
              </li>
            ))}
          </ul>

          {/* Example finding card */}
          <div className="mt-10 max-w-md rounded-2xl border border-white/10 bg-white/5 p-5 shadow-2xl shadow-black/40 backdrop-blur">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 rounded-full bg-amber-400/10 px-2.5 py-1 text-xs font-medium text-amber-300 ring-1 ring-amber-400/30">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
                Requirement drift
              </span>
              <span className="text-xs text-zinc-500">rule-detected</span>
            </div>
            <div className="mt-4 space-y-2 font-mono text-[13px]">
              <p className="text-zinc-300">
                <span className="text-indigo-300">REQ-17</span> → reset_password()
              </p>
              <p className="text-zinc-300">
                → test_reset_password() <span className="text-rose-300">not updated</span>
              </p>
            </div>
            <div className="mt-4 flex items-center justify-between border-t border-white/10 pt-3 text-xs">
              <span className="text-zinc-400">Potential test gap · review recommended</span>
              <span className="rounded-md bg-rose-500/10 px-2 py-0.5 font-medium text-rose-300">High</span>
            </div>
          </div>
        </section>

        {/* Right: login card */}
        <section className="flex justify-center lg:justify-end">
          <div className="w-full max-w-md rounded-3xl border border-white/10 bg-zinc-900/70 p-8 shadow-2xl shadow-black/50 backdrop-blur-xl sm:p-10">
            <div className="mb-8 flex items-center gap-2 lg:hidden">
              <ShieldIcon />
              <span className="text-lg font-semibold">ReqGuard</span>
            </div>

            <h2 className="text-2xl font-semibold tracking-tight">Welcome back</h2>
            <p className="mt-1.5 text-sm text-zinc-400">Sign in to your ReqGuard workspace.</p>

            <button
              type="button"
              onClick={() => setFormError("GitHub sign-in will be added with the GitHub integration.")}
              className="mt-7 flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:border-white/20 hover:bg-white/10"
            >
              <GitHubIcon />
              Continue with GitHub
            </button>

            <div className="my-6 flex items-center gap-3 text-xs uppercase tracking-wider text-zinc-500">
              <div className="h-px flex-1 bg-white/10" />
              or
              <div className="h-px flex-1 bg-white/10" />
            </div>

            <form onSubmit={handleSubmit} noValidate className="space-y-5">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-zinc-300">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  aria-invalid={!!errors.email}
                  className={`mt-1.5 w-full rounded-xl border bg-zinc-950/60 px-3.5 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-600 outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/20 ${
                    errors.email ? "border-rose-500/70" : "border-white/10"
                  }`}
                />
                {errors.email && <p className="mt-1.5 text-xs text-rose-400">{errors.email}</p>}
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <label htmlFor="password" className="block text-sm font-medium text-zinc-300">
                    Password
                  </label>
                  <a href="#" className="text-xs text-indigo-300 transition hover:text-indigo-200">
                    Forgot password?
                  </a>
                </div>
                <div className="relative mt-1.5">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    aria-invalid={!!errors.password}
                    className={`w-full rounded-xl border bg-zinc-950/60 px-3.5 py-2.5 pr-16 text-sm text-zinc-100 placeholder:text-zinc-600 outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/20 ${
                      errors.password ? "border-rose-500/70" : "border-white/10"
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    className="absolute inset-y-0 right-0 px-3.5 text-xs font-medium text-zinc-400 transition hover:text-zinc-100"
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
                {errors.password && <p className="mt-1.5 text-xs text-rose-400">{errors.password}</p>}
              </div>

              <label className="flex cursor-pointer items-center gap-2.5 text-sm text-zinc-400">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="h-4 w-4 rounded accent-indigo-500"
                />
                Remember me
              </label>

              {formError && (
                <p className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3.5 py-2.5 text-sm text-rose-300">
                  {formError}
                </p>
              )}
              {success && (
                <p className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3.5 py-2.5 text-sm text-emerald-300">
                  {success}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="group flex w-full items-center justify-center gap-2 rounded-xl bg-linear-to-r from-indigo-500 to-violet-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:from-indigo-400 hover:to-violet-400 hover:shadow-indigo-500/40 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading && <Spinner />}
                {loading ? "Signing in..." : "Sign in"}
                {!loading && <span className="transition group-hover:translate-x-0.5">→</span>}
              </button>
            </form>

            <p className="mt-8 text-center text-sm text-zinc-500">
              Don&apos;t have an account?{" "}
              <a href="#" className="font-medium text-indigo-300 transition hover:text-indigo-200">
                Create one
              </a>
            </p>
          </div>
        </section>
      </div>

      <p className="absolute inset-x-0 bottom-4 text-center text-xs text-zinc-600">
        © 2026 ReqGuard · Capstone Project
      </p>
    </main>
  );
}

function ShieldIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z" fill="#F59E0B" />
      <path d="m8.5 12 2.5 2.5 4.5-5" stroke="#18181B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m5 12 5 5 9-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 .5a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2.2c-3.3.7-4-1.4-4-1.4-.6-1.4-1.4-1.8-1.4-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1.1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.8-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0C17.3 4.6 18.3 5 18.3 5c.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 12 .5Z" />
    </svg>
  );
}
