"use client";

import { useEffect } from "react";
import {
  useFieldArray,
  useForm,
  useWatch,
  type FieldValues,
  type Path,
  type UseFormRegister,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { NodeDef } from "@/lib/journey-definition";
import type { JourneyNode } from "@/lib/journey-graph";
import {
  branchApply,
  branchDefaults,
  branchSchema,
  sendTemplateApply,
  sendTemplateDefaults,
  sendTemplateSchema,
  startApply,
  startDefaults,
  startSchema,
  UNITS,
  updateContactApply,
  updateContactDefaults,
  updateContactSchema,
  variableRows,
  waitApply,
  waitDefaults,
  waitForReplyApply,
  waitForReplyDefaults,
  waitForReplySchema,
  waitSchema,
  type Applied,
  type BranchValues,
  type SendTemplateValues,
  type StartValues,
  type Targets,
  type TemplateOption,
  type UpdateContactValues,
  type WaitForReplyValues,
  type WaitValues,
} from "@/lib/node-forms";

type Shared = { targets: Targets; options: string[]; onApply: (applied: Applied) => void };
type FormProps<T extends NodeDef["type"]> = Shared & { node: Extract<NodeDef, { type: T }> };

export function NodePanel({
  node,
  templates,
  onDelete,
  ...shared
}: Shared & { node: JourneyNode; templates: TemplateOption[]; onDelete: (id: string) => void }) {
  const data = node.data;
  return (
    <aside style={{ width: 320, fontSize: 14 }}>
      <h2>{data.type}</h2>
      <p>id: {node.id}</p>
      {data.type === "start" && <StartForm node={data} {...shared} />}
      {data.type === "send_template" && (
        <SendTemplateForm node={data} templates={templates} {...shared} />
      )}
      {data.type === "wait" && <WaitForm node={data} {...shared} />}
      {data.type === "wait_for_reply" && <WaitForReplyForm node={data} {...shared} />}
      {data.type === "branch" && <BranchForm node={data} {...shared} />}
      {data.type === "update_contact" && <UpdateContactForm node={data} {...shared} />}
      {data.type === "end" && <p>The journey ends here.</p>}
      <p>
        <button type="button" onClick={() => onDelete(node.id)}>
          Delete node
        </button>
      </p>
    </aside>
  );
}

function TargetSelect<T extends FieldValues>({
  label,
  name,
  register,
  options,
}: {
  label: string;
  name: Path<T>;
  register: UseFormRegister<T>;
  options: string[];
}) {
  return (
    <label style={{ display: "block" }}>
      {label}
      <select {...register(name)}>
        <option value="">(not connected)</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function DurationFields<T extends FieldValues>({
  label,
  amountName,
  unitName,
  register,
  error,
}: {
  label: string;
  amountName: Path<T>;
  unitName: Path<T>;
  register: UseFormRegister<T>;
  error?: string;
}) {
  return (
    <fieldset>
      <legend>{label}</legend>
      <label>
        Amount
        <input {...register(amountName)} inputMode="numeric" size={4} />
      </label>{" "}
      <label>
        Unit
        <select {...register(unitName)}>
          {UNITS.map((unit) => (
            <option key={unit} value={unit}>
              {unit}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="alert">{error}</p>}
    </fieldset>
  );
}

function StartForm({ node, targets, options, onApply }: FormProps<"start">) {
  const form = useForm<StartValues>({
    resolver: zodResolver(startSchema),
    defaultValues: startDefaults(targets),
  });
  return (
    <form onSubmit={form.handleSubmit((values) => onApply(startApply(node, values)))}>
      <TargetSelect label="Next node" name="next" register={form.register} options={options} />
      <button type="submit">Apply</button>
    </form>
  );
}

function SendTemplateForm({
  node,
  targets,
  options,
  templates,
  onApply,
}: FormProps<"send_template"> & { templates: TemplateOption[] }) {
  const form = useForm<SendTemplateValues>({
    resolver: zodResolver(sendTemplateSchema),
    defaultValues: sendTemplateDefaults(node, targets, templates),
  });
  const { fields, replace } = useFieldArray({ control: form.control, name: "variables" });
  const templateId = useWatch({ control: form.control, name: "template_id" });
  useEffect(() => {
    const count = templates.find((template) => template.id === templateId)?.placeholders ?? 0;
    if (count !== form.getValues("variables").length) {
      replace(variableRows(count, form.getValues("variables")));
    }
  }, [templateId, templates, form, replace]);
  return (
    <form onSubmit={form.handleSubmit((values) => onApply(sendTemplateApply(node, values)))}>
      <label style={{ display: "block" }}>
        Template
        <select {...form.register("template_id")}>
          <option value="">(choose an approved template)</option>
          {templates.map((template) => (
            <option key={template.id} value={template.id}>
              {template.name} ({template.language})
            </option>
          ))}
        </select>
      </label>
      {form.formState.errors.template_id && (
        <p role="alert">{form.formState.errors.template_id.message}</p>
      )}
      {fields.map((field, index) => (
        <label key={field.id} style={{ display: "block" }}>
          {`{{${index + 1}}}`} from
          <input {...form.register(`variables.${index}.path`)} placeholder="contact.first_name" />
          {form.formState.errors.variables?.[index]?.path && <span role="alert"> required</span>}
        </label>
      ))}
      <TargetSelect label="Next node" name="next" register={form.register} options={options} />
      <button type="submit">Apply</button>
    </form>
  );
}

function WaitForm({ node, targets, options, onApply }: FormProps<"wait">) {
  const form = useForm<WaitValues>({
    resolver: zodResolver(waitSchema),
    defaultValues: waitDefaults(node, targets),
  });
  return (
    <form onSubmit={form.handleSubmit((values) => onApply(waitApply(node, values)))}>
      <DurationFields
        label="Wait for"
        amountName="duration.amount"
        unitName="duration.unit"
        register={form.register}
        error={form.formState.errors.duration?.amount?.message}
      />
      <TargetSelect label="Next node" name="next" register={form.register} options={options} />
      <button type="submit">Apply</button>
    </form>
  );
}

function WaitForReplyForm({ node, targets, options, onApply }: FormProps<"wait_for_reply">) {
  const form = useForm<WaitForReplyValues>({
    resolver: zodResolver(waitForReplySchema),
    defaultValues: waitForReplyDefaults(node, targets),
  });
  return (
    <form onSubmit={form.handleSubmit((values) => onApply(waitForReplyApply(node, values)))}>
      <DurationFields
        label="Give up after"
        amountName="timeout.amount"
        unitName="timeout.unit"
        register={form.register}
        error={form.formState.errors.timeout?.amount?.message}
      />
      <TargetSelect label="On reply" name="onReply" register={form.register} options={options} />
      <TargetSelect
        label="On timeout"
        name="onTimeout"
        register={form.register}
        options={options}
      />
      <button type="submit">Apply</button>
    </form>
  );
}

function BranchForm({ node, targets, options, onApply }: FormProps<"branch">) {
  const form = useForm<BranchValues>({
    resolver: zodResolver(branchSchema),
    defaultValues: branchDefaults(node, targets),
  });
  const { fields, append, remove } = useFieldArray({ control: form.control, name: "conditions" });
  return (
    <form onSubmit={form.handleSubmit((values) => onApply(branchApply(node, values)))}>
      {fields.map((field, index) => (
        <fieldset key={field.id}>
          <legend>Condition {index + 1}</legend>
          <label style={{ display: "block" }}>
            Path
            <input
              {...form.register(`conditions.${index}.path`)}
              placeholder="reply.button_payload"
            />
            {form.formState.errors.conditions?.[index]?.path && <span role="alert"> required</span>}
          </label>
          <label style={{ display: "block" }}>
            Equals
            <input {...form.register(`conditions.${index}.value`)} placeholder="YES" />
          </label>
          <TargetSelect
            label="Then go to"
            name={`conditions.${index}.next`}
            register={form.register}
            options={options}
          />
          <button type="button" onClick={() => remove(index)}>
            Remove condition
          </button>
        </fieldset>
      ))}
      <p>
        <button type="button" onClick={() => append({ path: "", value: "", next: "" })}>
          Add condition
        </button>
      </p>
      <TargetSelect
        label="Otherwise go to"
        name="else"
        register={form.register}
        options={options}
      />
      <button type="submit">Apply</button>
    </form>
  );
}

function UpdateContactForm({ node, targets, options, onApply }: FormProps<"update_contact">) {
  const form = useForm<UpdateContactValues>({
    resolver: zodResolver(updateContactSchema),
    defaultValues: updateContactDefaults(node, targets),
  });
  const { fields, append, remove } = useFieldArray({ control: form.control, name: "set" });
  return (
    <form onSubmit={form.handleSubmit((values) => onApply(updateContactApply(node, values)))}>
      {fields.map((field, index) => (
        <p key={field.id}>
          <input {...form.register(`set.${index}.key`)} placeholder="attributes.interested" />
          {" = "}
          <input {...form.register(`set.${index}.value`)} placeholder="yes" />{" "}
          <button type="button" onClick={() => remove(index)}>
            Remove
          </button>
          {form.formState.errors.set?.[index]?.key && <span role="alert"> key required</span>}
        </p>
      ))}
      <p>
        <button type="button" onClick={() => append({ key: "", value: "" })}>
          Add field
        </button>
      </p>
      <TargetSelect label="Next node" name="next" register={form.register} options={options} />
      <button type="submit">Apply</button>
    </form>
  );
}
