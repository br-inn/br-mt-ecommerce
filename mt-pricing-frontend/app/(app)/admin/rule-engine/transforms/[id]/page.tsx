import { notFound } from "next/navigation"
import { LookupEditor } from "./lookup-editor"
import env from "@/lib/env"
import { createClient } from "@/lib/supabase/server"

const apiBase = process.env.BACKEND_URL ?? env.NEXT_PUBLIC_BACKEND_URL

async function authHeaders(): Promise<HeadersInit> {
  const supabase = await createClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  if (!session?.access_token) return {}
  return { Authorization: `Bearer ${session.access_token}` }
}

export default async function TransformEditPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const headers = await authHeaders()
  const res = await fetch(
    `${apiBase}/api/v1/rule-engine/unit-transforms/${id}`,
    { cache: "no-store", headers },
  )
  if (!res.ok) notFound()
  const transform = await res.json()

  return <LookupEditor transform={transform} />
}
