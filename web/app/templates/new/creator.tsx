"use client";

import { useEffect, useState, useTransition, type ReactNode } from "react";
import {
  useFieldArray,
  useForm,
  useWatch,
  type FieldValues,
  type Path,
  type UseFormRegister,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  bodyProblems,
  exampleRows,
  HEADER_KINDS,
  LANGUAGES,
  nameProblem,
  serviceDefaults,
  serviceSchema,
  templateDefaults,
  templateSchema,
  toServiceSpec,
  toTemplateSpec,
  variablesOf,
  type ServiceValues,
  type TemplateValues,
} from "@/lib/template-rules";
import { saveServiceMessage, saveTemplate } from "./actions";

type Kind = "template" | "service";

const HEADER_LABELS: Record<(typeof HEADER_KINDS)[number], string> = {
  none: "No header",
  text: "Text",
  image: "Image",
};

/** Two steps: the kind and a unique name, then the form that kind needs. */
export function Creator({ takenNames }: { takenNames: string[] }) {
  const [kind, setKind] = useState<Kind | null>(null);
  const [name, setName] = useState("");
  const [step, setStep] = useState<1 | 2>(1);
  const problem = name === "" ? null : nameProblem(name, new Set(takenNames));
  const ready = kind !== null && name !== "" && problem === null;
  return (
    <div className="creator">
      <section className="card pad">
        <ol className="stepper">
          <li aria-current={step === 1 ? "step" : undefined}>Type and name</li>
          <li aria-current={step === 2 ? "step" : undefined}>Content</li>
        </ol>
        {step === 1 && (
          <>
            <div className="type-tiles" role="group" aria-label="Type">
              <TypeTile
                title="Template"
                text="Reviewed by Meta; can start a conversation at any time; paid per delivered message."
                selected={kind === "template"}
                onSelect={() => setKind("template")}
                icon={<TemplateIcon />}
              />
              <TypeTile
                title="Service message"
                text="Plain text with an optional image; only within 24 hours of the contact's last message; no review."
                selected={kind === "service"}
                onSelect={() => setKind("service")}
                icon={<ChatIcon />}
              />
            </div>
            <label>
              Name
              <input
                value={name}
                onChange={(event) => setName(event.target.value.trim())}
                placeholder="welcome_offer_1"
                autoComplete="off"
              />
            </label>
            {problem && <p role="alert">{problem}</p>}
            <p className="hint">
              Lowercase letters, digits and underscores; the name must be unique. Meta blocks the
              name of a deleted approved template for 30 days.
            </p>
            <div className="toolbar">
              <button type="button" disabled={!ready} onClick={() => setStep(2)}>
                Next
              </button>
            </div>
          </>
        )}
        {step === 2 && kind === "template" && (
          <TemplateForm name={name} onBack={() => setStep(1)} />
        )}
        {step === 2 && kind === "service" && <ServiceForm name={name} onBack={() => setStep(1)} />}
      </section>
      <aside className="card pad rules" aria-label="Meta's rules">
        <h2>What Meta accepts</h2>
        <ul>
          <li>
            Variables as <code>{"{{first_name}}"}</code>: not at the start or end of the body, never
            two in a row, each with an example value for the reviewers.
          </li>
          <li>
            UTILITY is for confirmations, reminders and updates the contact expects; promotional
            wording gets a template re-categorised as MARKETING, which costs about three times more.
          </li>
          <li>Header: up to 60 characters of text, or an image from a public https address.</li>
          <li>Footer: up to 60 characters. Buttons: up to 5, at most 2 with a link.</li>
          <li>Emoji are fine in the body, the header and the buttons.</li>
          <li>
            A service message is free inside the 24-hour window after the contact&apos;s last
            message (1000 a month per number); outside it the journey skips or fails the node.
          </li>
        </ul>
      </aside>
    </div>
  );
}

function TypeTile({
  title,
  text,
  selected,
  onSelect,
  icon,
}: {
  title: string;
  text: string;
  selected: boolean;
  onSelect: () => void;
  icon: ReactNode;
}) {
  return (
    <button
      type="button"
      className="type-tile"
      aria-pressed={selected}
      aria-label={title}
      onClick={onSelect}
    >
      <span className="icon" aria-hidden="true">
        {icon}
      </span>
      <span>
        <strong>{title}</strong>
        <span className="muted">{text}</span>
      </span>
    </button>
  );
}

function Problem({ message }: { message?: string }) {
  return message ? <p role="alert">{message}</p> : null;
}

function LanguageSelect<T extends FieldValues>({
  name,
  register,
}: {
  name: Path<T>;
  register: UseFormRegister<T>;
}) {
  return (
    <label>
      Language
      <select {...register(name)}>
        {LANGUAGES.map((language) => (
          <option key={language.code} value={language.code}>
            {language.label} ({language.code})
          </option>
        ))}
      </select>
    </label>
  );
}

function TemplateForm({ name, onBack }: { name: string; onBack: () => void }) {
  const [pending, start] = useTransition();
  const [failure, setFailure] = useState<string | null>(null);
  const form = useForm<TemplateValues>({
    resolver: zodResolver(templateSchema),
    defaultValues: templateDefaults,
  });
  const examples = useFieldArray({ control: form.control, name: "example_values" });
  const buttons = useFieldArray({ control: form.control, name: "buttons" });
  const body = useWatch({ control: form.control, name: "body" }) ?? "";
  const headerKind = useWatch({ control: form.control, name: "header_kind" });
  const buttonRows = useWatch({ control: form.control, name: "buttons" }) ?? [];
  useEffect(() => {
    const current = form.getValues("example_values");
    const rows = exampleRows(body, current);
    if (rows.length !== current.length) examples.replace(rows);
  }, [body, form, examples]);
  const variables = variablesOf(body);
  const problems = bodyProblems(body);
  const errors = form.formState.errors;
  const submit = (values: TemplateValues) =>
    start(async () => {
      setFailure(await saveTemplate(toTemplateSpec(name, values)));
    });
  return (
    <form onSubmit={form.handleSubmit(submit)} className="stack">
      <p className="muted">
        Template <strong>{name}</strong>
      </p>
      <div className="field-row">
        <LanguageSelect name="language" register={form.register} />
        <label>
          Category
          <select {...form.register("category")}>
            <option value="UTILITY">UTILITY (confirmations, reminders)</option>
            <option value="MARKETING">MARKETING (offers, news)</option>
          </select>
        </label>
      </div>
      <fieldset>
        <legend>Header</legend>
        <div className="field-row">
          {HEADER_KINDS.map((option) => (
            <label key={option} className="inline">
              <input type="radio" value={option} {...form.register("header_kind")} />
              {HEADER_LABELS[option]}
            </label>
          ))}
        </div>
        {headerKind === "text" && (
          <label>
            Header text
            <input {...form.register("header")} maxLength={60} placeholder="Nowa akcja" />
          </label>
        )}
        {headerKind === "image" && (
          <label>
            Image address (https, JPEG or PNG, up to 5 MB)
            <input {...form.register("header_image_url")} placeholder="https://…/image.png" />
          </label>
        )}
        <Problem message={errors.header?.message ?? errors.header_image_url?.message} />
      </fieldset>
      <label>
        Body
        <textarea
          {...form.register("body")}
          rows={6}
          placeholder="Cześć {{first_name}}, dziękujemy za wsparcie 🙏"
        />
      </label>
      {problems.length > 0 && (
        <ul className="problems" aria-label="Body problems">
          {problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}
      <Problem message={errors.body?.message} />
      {examples.fields.map((field, index) => (
        <label key={field.id}>
          {`Example for {{${variables[index] ?? ""}}}`}
          <input {...form.register(`example_values.${index}.value`)} placeholder="Ala" />
          <Problem message={errors.example_values?.[index]?.value?.message} />
        </label>
      ))}
      <label>
        Footer (optional)
        <input
          {...form.register("footer")}
          maxLength={60}
          placeholder="Odpowiedz STOP, aby zrezygnować"
        />
      </label>
      <Problem message={errors.footer?.message} />
      <fieldset>
        <legend>Buttons (up to 5, at most 2 with a link)</legend>
        {buttons.fields.map((field, index) => (
          <div key={field.id} className="field-row">
            <label>
              Type
              <select {...form.register(`buttons.${index}.type`)}>
                <option value="quick_reply">Quick reply</option>
                <option value="url">Link</option>
              </select>
            </label>
            <label>
              Text
              <input {...form.register(`buttons.${index}.text`)} maxLength={25} placeholder="Tak" />
            </label>
            {buttonRows[index]?.type === "url" && (
              <label>
                Address
                <input {...form.register(`buttons.${index}.url`)} placeholder="https://…" />
              </label>
            )}
            <button type="button" className="secondary" onClick={() => buttons.remove(index)}>
              Remove
            </button>
            <Problem
              message={
                errors.buttons?.[index]?.text?.message ?? errors.buttons?.[index]?.url?.message
              }
            />
          </div>
        ))}
        {buttons.fields.length < 5 && (
          <button
            type="button"
            className="secondary"
            onClick={() => buttons.append({ type: "quick_reply", text: "", url: "" })}
          >
            Add button
          </button>
        )}
        <Problem message={errors.buttons?.message ?? errors.buttons?.root?.message} />
      </fieldset>
      {failure && <p role="alert">{failure}</p>}
      <div className="toolbar">
        <button type="button" className="secondary" onClick={onBack}>
          Back
        </button>
        <button type="submit" disabled={pending}>
          {pending ? "Saving…" : "Save draft"}
        </button>
      </div>
    </form>
  );
}

function ServiceForm({ name, onBack }: { name: string; onBack: () => void }) {
  const [pending, start] = useTransition();
  const [failure, setFailure] = useState<string | null>(null);
  const form = useForm<ServiceValues>({
    resolver: zodResolver(serviceSchema),
    defaultValues: serviceDefaults,
  });
  const errors = form.formState.errors;
  const submit = (values: ServiceValues) =>
    start(async () => {
      setFailure(await saveServiceMessage(toServiceSpec(name, values)));
    });
  return (
    <form onSubmit={form.handleSubmit(submit)} className="stack">
      <p className="muted">
        Service message <strong>{name}</strong>
      </p>
      <LanguageSelect name="language" register={form.register} />
      <label>
        Image address (optional, https)
        <input {...form.register("image_url")} placeholder="https://…/image.png" />
      </label>
      <Problem message={errors.image_url?.message} />
      <label>
        Body (no variables; emoji are fine)
        <textarea {...form.register("body")} rows={6} placeholder="Dziękujemy za odpowiedź 🙏" />
      </label>
      <Problem message={errors.body?.message} />
      {failure && <p role="alert">{failure}</p>}
      <div className="toolbar">
        <button type="button" className="secondary" onClick={onBack}>
          Back
        </button>
        <button type="submit" disabled={pending}>
          {pending ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}

function TemplateIcon() {
  return (
    <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="7" y="5" width="26" height="30" rx="4" />
      <path d="M13 13h14M13 19h14M13 25h9" strokeLinecap="round" />
      <path d="M26 29l3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="2">
      <path
        d="M8 10a4 4 0 0 1 4-4h16a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4H17l-7 6v-6a4 4 0 0 1-2-3.5V10z"
        strokeLinejoin="round"
      />
      <path d="M14 13h12M14 19h8" strokeLinecap="round" />
    </svg>
  );
}
