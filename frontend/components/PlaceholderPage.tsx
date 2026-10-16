// Empty page used until the feature for this section is built.

type Props = {
  title: string;
  description: string;
  step: number; // BUILD_PLAN step that builds this page
};

export default function PlaceholderPage({ title, description, step }: Props) {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-1.5 text-sm text-zinc-400">{description}</p>

      <div className="mt-8 rounded-2xl border border-dashed border-white/10 p-10 text-center text-sm text-zinc-500">
        Coming in Step {step}
      </div>
    </div>
  );
}
