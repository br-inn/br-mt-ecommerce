"use client"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface ProfileCardProps {
  family: string
  totalMatches?: number
  confirmationRate?: number | null
  fpRate?: number | null
  pendingSuggestions?: number
}

export function ProfileCard({ family, totalMatches, confirmationRate, fpRate, pendingSuggestions }: ProfileCardProps) {
  const hasSuggestions = (pendingSuggestions ?? 0) > 0
  const highFpRate = fpRate !== null && fpRate !== undefined && fpRate > 0.15

  return (
    <Link href={`/admin/rule-engine/${encodeURIComponent(family)}`}>
      <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-mono">{family}</CardTitle>
            <div className="flex gap-1">
              {hasSuggestions && (
                <Badge variant="outline" className="text-yellow-600 border-yellow-400">
                  {pendingSuggestions} sugerencias
                </Badge>
              )}
              {highFpRate && <Badge variant="destructive">FP alto</Badge>}
            </div>
          </div>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground grid grid-cols-3 gap-2">
          <div>
            <div className="font-medium text-foreground">{totalMatches ?? "—"}</div>
            <div>matches (30d)</div>
          </div>
          <div>
            <div className="font-medium text-foreground">
              {confirmationRate !== null && confirmationRate !== undefined
                ? `${(confirmationRate * 100).toFixed(0)}%`
                : "—"}
            </div>
            <div>confirmación</div>
          </div>
          <div>
            <div className={`font-medium ${highFpRate ? "text-destructive" : "text-foreground"}`}>
              {fpRate !== null && fpRate !== undefined ? `${(fpRate * 100).toFixed(0)}%` : "—"}
            </div>
            <div>FP rate</div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
