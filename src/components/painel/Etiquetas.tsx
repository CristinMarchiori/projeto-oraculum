import type { Prioridade, Status } from "@/lib/notas";

const statusClasses: Record<Status, string> = {
  Aberta: "bg-status-aberta/12 text-status-aberta border-status-aberta/30",
  "Em andamento": "bg-status-andamento/15 text-status-andamento border-status-andamento/35",
  Concluída: "bg-status-concluida/12 text-status-concluida border-status-concluida/30",
};

const prioridadeClasses: Record<Prioridade, string> = {
  Baixa: "bg-muted text-muted-foreground border-border",
  Média: "bg-accent text-accent-foreground border-accent-foreground/20",
  Alta: "bg-status-andamento/15 text-status-andamento border-status-andamento/35",
  Crítica: "bg-status-critica/12 text-status-critica border-status-critica/30",
};

const base =
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap";

export function EtiquetaStatus({ status }: { status: Status }) {
  return (
    <span className={`${base} ${statusClasses[status]}`}>
      <span className="size-1.5 rounded-full bg-current" />
      {status}
    </span>
  );
}

export function EtiquetaPrioridade({ prioridade }: { prioridade: Prioridade }) {
  return <span className={`${base} ${prioridadeClasses[prioridade]}`}>{prioridade}</span>;
}
