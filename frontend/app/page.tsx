import { redirect } from "next/navigation";

// The home page has no content of its own; send users to the project list.
export default function Home() {
  redirect("/projects");
}
