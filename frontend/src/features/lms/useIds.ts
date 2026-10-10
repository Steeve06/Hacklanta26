import { useParams } from "react-router-dom";

export function useNumericParam(name: string): number {
  const params = useParams();
  const value = Number(params[name]);
  if (!Number.isInteger(value) || value <= 0) throw new Response("Not found", { status: 404 });
  return value;
}
