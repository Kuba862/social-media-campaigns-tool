import Link from "next/link";
import { Nav } from "@/components/nav";
import { ApiError, apiFetch } from "@/lib/api";
import type { TemplateRow } from "@/lib/templates";
import { Creator } from "./creator";

export default async function NewTemplatePage() {
  let names: string[] = [];
  let problem: string | null = null;
  try {
    names = (await apiFetch<TemplateRow[]>("/templates")).map((row) => row.name);
  } catch (error) {
    problem = error instanceof ApiError ? error.message : "API is not reachable";
  }
  return (
    <>
      <Nav current="/templates" />
      <main>
        <p className="crumbs">
          <Link href="/templates">Templates</Link> / New
        </p>
        <div className="page-head">
          <div>
            <h1>New message</h1>
            <p className="lede">
              A template goes to Meta for approval and can open a conversation; a service message is
              sent inside 24 hours of the contact&apos;s last message and needs no approval.
            </p>
          </div>
        </div>
        {problem && <p role="alert">{problem}</p>}
        <Creator takenNames={names} />
      </main>
    </>
  );
}
