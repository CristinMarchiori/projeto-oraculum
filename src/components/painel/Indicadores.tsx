import { AlertTriangle, CheckCircle2, ClipboardList, Loader2 } from "lucide-react";
import type { Nota } from "@/lib/notas";

interface Props {
  notas: Nota[];
}

export function Indicadores({ notas }: Props) {
  const cards = [
    {
      titulo: "Notas abertas",
      valor: notas.filter((n) => n.status === "Aberta").length,
      Icone: ClipboardList,
      cor: "text-status-aberta",
      fundo: "bg-status-aberta/10",
    },
    {
      titulo: "Notas em andamento",
      valor: notas.filter((n) => n.status === "Em andamento").length,
      Icone: Loader2,
      cor: "text-status-andamento",
      fundo: "bg-status-andamento/10",
    },
    {
      titulo: "Notas concluídas",
      valor: notas.filter((n) => n.status === "Concluída").length,
      Icone: CheckCircle2,
      cor: "text-status-concluida",
      fundo: "bg-status-concluida/10",
    },
    {
      titulo: "Notas críticas",
      valor: notas.filter((n) => n.prioridade === "Crítica").length,
      Icone: AlertTriangle,
      cor: "text-status-critica",
      fundo: "bg-status-critica/10",
    },
  ];

  return (
    <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map(({ titulo, valor, Icone, cor, fundo }) => (
        <div key={titulo} className="panel flex items-center gap-4 p-5">
          <span className={`flex size-11 items-center justify-center rounded-md ${fundo} ${cor}`}>
            <Icone className="size-5" />
          </span>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {titulo}
            </p>
            <p className="font-display text-3xl font-bold leading-tight text-foreground">{valor}</p>
          </div>
        </div>
      ))}
    </section>
  );
}
