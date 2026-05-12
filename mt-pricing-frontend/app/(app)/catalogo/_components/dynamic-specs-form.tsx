"use client";

import * as React from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  SpecsSchema,
  SpecsSchemaProperty,
} from "@/lib/api/endpoints/specs";
import { cn } from "@/lib/utils/cn";

interface DynamicSpecsFormProps {
  schema: SpecsSchema;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
  errors?: Record<string, string>;
  className?: string;
}

/**
 * Renders a form whose fields are derived from a JSON Schema describing the
 * `products.specs` JSONB shape for a given family. Validation is server-side;
 * this component only collects values and surfaces `errors` per field.
 *
 * Supported property kinds:
 *  - `enum` (string) → Select
 *  - `type: "number" | "integer"` → number input
 *  - `type: "boolean"` → checkbox
 *  - `type: "string"` (no enum) → text input
 *  - Nested objects → flattened with "parent.child" key (one level deep)
 *  - Arrays / unknown types → JSON text input (escape hatch)
 */
export function DynamicSpecsForm({
  schema,
  value,
  onChange,
  errors,
  className,
}: DynamicSpecsFormProps) {
  const properties = schema.properties ?? {};
  const required = new Set(schema.required ?? []);
  const keys = Object.keys(properties);

  if (keys.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No structured spec fields are defined for this family yet.
      </p>
    );
  }

  const setField = (key: string, fieldValue: unknown) => {
    onChange({ ...value, [key]: fieldValue });
  };

  return (
    <div className={cn("grid gap-4 sm:grid-cols-2", className)}>
      {keys.map((key) => {
        const property = properties[key];
        if (!property) return null;
        return (
          <DynamicSpecsField
            key={key}
            name={key}
            property={property}
            value={value[key]}
            required={required.has(key)}
            error={errors?.[key]}
            onChange={(v) => setField(key, v)}
          />
        );
      })}
    </div>
  );
}

interface FieldProps {
  name: string;
  property: SpecsSchemaProperty;
  value: unknown;
  required: boolean;
  error: string | undefined;
  onChange: (value: unknown) => void;
}

function DynamicSpecsField({
  name,
  property,
  value,
  required,
  error,
  onChange,
}: FieldProps) {
  const label = property.title ?? name;
  const fieldId = `specs-${name}`;
  const propertyType = Array.isArray(property.type)
    ? property.type[0]
    : property.type;

  let control: React.ReactNode;
  if (property.enum && property.enum.length > 0) {
    const stringValue = value == null ? "" : String(value);
    control = (
      <Select
        value={stringValue}
        onValueChange={(v) => onChange(v === "" ? null : v)}
      >
        <SelectTrigger id={fieldId}>
          <SelectValue placeholder="—" />
        </SelectTrigger>
        <SelectContent>
          {property.enum.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  } else if (propertyType === "number" || propertyType === "integer") {
    control = (
      <Input
        id={fieldId}
        type="number"
        inputMode="decimal"
        step={propertyType === "integer" ? 1 : "any"}
        value={value == null ? "" : String(value)}
        onChange={(event) => {
          const raw = event.target.value;
          if (raw === "") {
            onChange(null);
            return;
          }
          const parsed = propertyType === "integer"
            ? Number.parseInt(raw, 10)
            : Number.parseFloat(raw);
          onChange(Number.isNaN(parsed) ? raw : parsed);
        }}
      />
    );
  } else if (propertyType === "boolean") {
    control = (
      <input
        id={fieldId}
        type="checkbox"
        checked={value === true}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 rounded border-input"
      />
    );
  } else if (propertyType === "object" && property.properties) {
    const nested = (value as Record<string, unknown> | undefined) ?? {};
    return (
      <fieldset className="sm:col-span-2 rounded-md border border-border/60 p-3">
        <legend className="px-1 text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.keys(property.properties).map((childKey) => {
            const childProperty = property.properties![childKey];
            if (!childProperty) return null;
            return (
              <DynamicSpecsField
                key={childKey}
                name={`${name}.${childKey}`}
                property={childProperty}
                value={nested[childKey]}
                required={(property.required ?? []).includes(childKey)}
                error={undefined}
                onChange={(childValue) => {
                  onChange({ ...nested, [childKey]: childValue });
                }}
              />
            );
          })}
        </div>
      </fieldset>
    );
  } else if (propertyType === "array") {
    const stringValue = Array.isArray(value)
      ? JSON.stringify(value)
      : value == null
        ? ""
        : String(value);
    control = (
      <Input
        id={fieldId}
        value={stringValue}
        placeholder='["a","b"]'
        onChange={(event) => {
          const raw = event.target.value;
          if (raw === "") {
            onChange(null);
            return;
          }
          try {
            onChange(JSON.parse(raw));
          } catch {
            onChange(raw);
          }
        }}
      />
    );
  } else {
    control = (
      <Input
        id={fieldId}
        value={value == null ? "" : String(value)}
        onChange={(event) => {
          const raw = event.target.value;
          onChange(raw === "" ? null : raw);
        }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={fieldId} className="text-xs">
        {label}
        {required ? <span className="text-destructive ml-0.5">*</span> : null}
        {property.description ? (
          <span className="ml-2 text-muted-foreground font-normal">
            {property.description}
          </span>
        ) : null}
      </Label>
      {control}
      {error ? (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
