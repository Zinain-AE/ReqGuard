// Layout for every page that shows the sidebar.
// "(dashboard)" is a route group: it is not part of the URL, so pages stay at /projects, /sources, ...
// /login lives outside this group and so has no sidebar.

import Sidebar from "@/components/Sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-zinc-950 text-zinc-100">
      <Sidebar />
      <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
    </div>
  );
}
