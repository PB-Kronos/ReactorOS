import { useCallback, useState, type Dispatch, type SetStateAction } from "react";

type Scalar = number | boolean | string;
type Mode = "released" | "saved" | "persistent";
type Binding = {
  value: unknown;
  kind: "number" | "boolean" | "string" | "readonly";
  default?: Mode;
  bounds?: [number, number];
  choices?: readonly string[];
  apply?: (value: Scalar) => void;
  reset?: () => void;
};

export type PlantVariables = {
  bindings: Record<string, Binding>;
  holds: Record<string, Scalar>;
};

export function usePlantVariable<T extends Scalar>(
  registry: PlantVariables, name: string, initial: T | (() => T),
  mode: Mode = "released", bounds?: [number, number], choices?: readonly string[],
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState(initial);
  const set = useCallback<Dispatch<SetStateAction<T>>>((next) => {
    setValue(previous => {
      if (Object.prototype.hasOwnProperty.call(registry.holds, name)) return registry.holds[name] as T;
      return typeof next === "function" ? next(previous) : next;
    });
  }, [registry, name]);
  registry.bindings[name] = {
    value, kind: choices ? "string" : typeof value === "number" ? "number" : "boolean", default: mode, bounds, choices,
    apply: next => setValue(next as T),
    reset: () => setValue(initial),
  };
  return [value, set];
}
