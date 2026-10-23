import { type Control, Controller, type FieldErrors, type UseFormRegister } from "react-hook-form";

import { options } from "@/lib/labels";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select } from "@/ui/input";

export interface AccountValues {
  name: string;
  from_name: string;
  from_address: string;
  reply_to: string;
  host: string;
  port: string;
  security: string;
  username: string;
  password: string;
  is_active: boolean;
}

export const emptyAccount = (): AccountValues => ({
  name: "", from_name: "", from_address: "", reply_to: "", host: "", port: "587", security: "STARTTLS",
  username: "", password: "", is_active: true,
});

export const ACCOUNT_FIELDS = ["name", "from_name", "from_address", "reply_to", "host", "port", "security", "username", "password"] as const;

/** Body for create and update; an empty password means "keep the stored one" on update. */
export function accountBody(v: AccountValues) {
  const blank = (s: string) => s.trim() || null;
  return {
    name: v.name.trim(),
    from_name: blank(v.from_name),
    from_address: v.from_address.trim(),
    reply_to: blank(v.reply_to),
    host: v.host.trim(),
    port: Number(v.port),
    security: v.security as "STARTTLS",
    username: blank(v.username),
    password: v.password ? v.password : null,
    is_active: v.is_active,
  };
}

export function AccountFields({ register, control, errors, editing, hasPassword }: {
  register: UseFormRegister<AccountValues>;
  control: Control<AccountValues>;
  errors: FieldErrors<AccountValues>;
  editing: boolean;
  hasPassword?: boolean;
}) {
  return (
    <>
      <Section title="Sender">
        <FieldGrid>
          <Field label="Name" required help="Internal name, e.g. Marketing IIT." error={errors.name?.message}>
            {(p) => <Input {...p} maxLength={100} {...register("name", { required: "Enter a name." })} />}
          </Field>
          <Field label="From Name" help="Shown as the sender; an edition's sender name wins." error={errors.from_name?.message}>
            {(p) => <Input {...p} maxLength={200} {...register("from_name")} />}
          </Field>
          <Field label="From Address" required error={errors.from_address?.message}>
            {(p) => <Input {...p} type="email" {...register("from_address", { required: "Enter the sender address." })} />}
          </Field>
          <Field label="Reply-To" error={errors.reply_to?.message}>
            {(p) => <Input {...p} type="email" {...register("reply_to")} />}
          </Field>
          <Controller
            control={control}
            name="is_active"
            render={({ field }) => (
              <div className="flex flex-col gap-1.5">
                <span className="text-[13px] text-label">Status</span>
                <label className="flex h-8 items-center gap-2 text-[14px]">
                  <Checkbox checked={field.value} onCheckedChange={(c) => field.onChange(c === true)} />
                  Active
                </label>
              </div>
            )}
          />
        </FieldGrid>
      </Section>
      <Section title="SMTP server">
        <FieldGrid>
          <Field label="Host" required help="e.g. smtp.gmail.com" error={errors.host?.message}>
            {(p) => <Input {...p} autoComplete="off" {...register("host", { required: "Enter the SMTP host." })} />}
          </Field>
          <Field label="Port" required error={errors.port?.message}>
            {(p) => <Input {...p} type="number" min={1} max={65535} {...register("port", { required: "Enter the port." })} />}
          </Field>
          <Field label="Security" required>
            {(p) => (
              <Select {...p} {...register("security")}>
                {options("smtp_security").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Username" help="Usually the full email address." error={errors.username?.message}>
            {(p) => <Input {...p} autoComplete="off" {...register("username")} />}
          </Field>
          <Field
            label="Password"
            help={editing ? (hasPassword ? "Stored and hidden. Leave empty to keep it." : "No password stored.") : "Gmail and Microsoft 365 need an app password."}
            error={errors.password?.message}
          >
            {(p) => <Input {...p} type="password" autoComplete="new-password" {...register("password")} />}
          </Field>
        </FieldGrid>
      </Section>
    </>
  );
}
