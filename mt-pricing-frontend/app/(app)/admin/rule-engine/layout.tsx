export default function RuleEngineLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="container mx-auto py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Motor de Reglas de Matching</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Configura los criterios y pesos para el pipeline de matching de productos.
        </p>
      </div>
      {children}
    </div>
  )
}
