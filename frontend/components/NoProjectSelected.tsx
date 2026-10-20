import Link from "next/link";

// Shown on project-scoped pages when no project is chosen in the sidebar.
export default function NoProjectSelected() {
  return (
    <div className="mt-8 rounded-2xl border border-dashed border-white/10 p-10 text-center text-sm text-zinc-400">
      Choose a project in the sidebar, or{" "}
      <Link href="/projects" className="text-indigo-300 hover:text-indigo-200">
        create one
      </Link>{" "}
      first.
    </div>
  );
}
